from __future__ import annotations

from pathlib import Path

import pandas as pd
from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from config.settings import BASE_DIR
from core.auth import autenticar_admin
from services.financeiro_conciliacao_service import (
    label_status,
    label_tipo,
    listar_movimentacoes_financeiras,
    mes_atual,
    meses_disponiveis,
    montar_conciliacao,
    resumo_financeiro,
    salvar_planilha_pessoas,
    salvar_pessoa_filhe,
    sincronizar_planilha_com_cadastro,
)
from services.financeiro_service import atualizar_status_comprovante, format_brl_value, listar_comprovantes
from services.faltas_service import listar_faltas
from services.limpeza_service import listar_limpeza
from services.pac_service import listar_criancas_pac, listar_filhos_por_responsavel, listar_pac_cadastros, listar_responsaveis_pac
from services.assinatura_service import BATCHES, historico_assinaturas
from services.portal_auth_service import atualizar_status_usuario_portal, listar_solicitacoes_portal
from app.routes.helpers import admin_required, df_records, excel_response, normalize_file_path

bp = Blueprint("admin", __name__)


PAID_STATUSES = {"pago", "aprovado", "aprovados", "paid"}


def _as_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "t", "1", "sim", "yes", "y"])


def _finance_summary(df: pd.DataFrame) -> dict:
    """Resumo financeiro robusto para status pago/aprovado x pendente."""
    if df is None or df.empty:
        return {
            "total": 0,
            "valor_total": 0,
            "valor_pago": 0,
            "valor_pendente": 0,
            "pendentes": 0,
            "aprovados": 0,
        }

    tmp = df.copy()
    valores = pd.to_numeric(tmp.get("valor_informado"), errors="coerce").fillna(0) if "valor_informado" in tmp else pd.Series([0] * len(tmp))
    status_norm = tmp.get("status", pd.Series([""] * len(tmp))).astype(str).str.strip().str.lower()
    pago_mask = status_norm.isin(PAID_STATUSES)
    pendente_mask = ~pago_mask

    return {
        "total": int(len(tmp)),
        "valor_total": float(valores.sum()),
        "valor_pago": float(valores[pago_mask].sum()),
        "valor_pendente": float(valores[pendente_mask].sum()),
        "pendentes": int(pendente_mask.sum()),
        "aprovados": int(pago_mask.sum()),
    }


def _pac_summary(cadastros: pd.DataFrame, criancas: pd.DataFrame) -> dict:
    """Big numbers do PAC conforme regra solicitada."""
    cad = cadastros.copy() if cadastros is not None else pd.DataFrame()
    cri = criancas.copy() if criancas is not None else pd.DataFrame()

    qtd_pessoas = 0
    qtd_menores = 0
    if not cad.empty:
        cpf_col = "cpf" if "cpf" in cad.columns else "id"
        qtd_pessoas = int(cad[cpf_col].dropna().astype(str).nunique())
        if "menor_idade" in cad.columns:
            menores = cad[_as_bool_series(cad["menor_idade"])]
        elif "idade" in cad.columns:
            menores = cad[pd.to_numeric(cad["idade"], errors="coerce").fillna(999) < 18]
        else:
            menores = pd.DataFrame()
        qtd_menores = int(menores[cpf_col].dropna().astype(str).nunique()) if not menores.empty else 0

    qtd_apadrinhados = 0
    qtd_nao_apadrinhados = 0
    if not cri.empty:
        child_col = "crianca_cpf" if "crianca_cpf" in cri.columns else ("cpf" if "cpf" in cri.columns else "id")
        if "padrinho_cpf" in cri.columns:
            padrinho = cri["padrinho_cpf"].astype(str).str.strip()
            apad = cri[padrinho.ne("") & padrinho.str.lower().ne("none") & cri["padrinho_cpf"].notna()]
            nao = cri[~cri.index.isin(apad.index)]
        elif "apadrinhamento" in cri.columns:
            status = cri["apadrinhamento"].astype(str).str.lower()
            apad = cri[status.str.contains("apadrinhada") & ~status.str.contains("não") & ~status.str.contains("nao")]
            nao = cri[~cri.index.isin(apad.index)]
        else:
            apad = pd.DataFrame()
            nao = cri
        qtd_apadrinhados = int(apad[child_col].dropna().astype(str).nunique()) if not apad.empty else 0
        qtd_nao_apadrinhados = int(nao[child_col].dropna().astype(str).nunique()) if not nao.empty else 0

    return {
        "pessoas": qtd_pessoas,
        "menores": qtd_menores,
        "apadrinhados": qtd_apadrinhados,
        "nao_apadrinhados": qtd_nao_apadrinhados,
    }


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin = autenticar_admin(request.form.get("usuario"), request.form.get("senha"))
        if admin:
            session["admin_logado"] = True
            session["admin"] = admin
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("admin.financeiro"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin/login.html")


@bp.get("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("admin.login"))


@bp.get("/")
@admin_required
def dashboard():
    return redirect(url_for("admin.financeiro"))


@bp.get("/pac")
@admin_required
def pac():
    return redirect(url_for("admin_pac.login"))


@bp.get("/pac/export/<kind>")
@admin_required
def pac_export(kind: str):
    if kind == "responsaveis":
        return excel_response(listar_responsaveis_pac(), "pac_maes_responsaveis.xlsx")
    if kind == "criancas":
        return excel_response(listar_criancas_pac(), "pac_criancas.xlsx")
    return excel_response(listar_pac_cadastros(), "pac_cadastros.xlsx")


@bp.get("/assinaturas")
@admin_required
def assinaturas():
    batch = request.args.get("batch") or None
    if batch and batch not in BATCHES:
        batch = None
    return render_template(
        "admin/assinaturas.html",
        rows=historico_assinaturas(batch),
        batches=BATCHES,
        selected_batch=batch,
    )


@bp.route("/financeiro", methods=["GET", "POST"])
@admin_required
def financeiro():
    if request.method == "POST":
        try:
            action = request.form.get("action")
            if action in {"salvar_pessoa", "adicionar_pessoa", "salvar_linha"}:
                salvar_pessoa_filhe(
                    cadastro_id=request.form.get("cadastro_id"),
                    nome=request.form.get("nome"),
                    cpf=request.form.get("cpf"),
                    telefone=request.form.get("telefone"),
                    email=request.form.get("email"),
                    data_nascimento=request.form.get("data_nascimento"),
                )
                comprovante_id_linha = request.form.get("comprovante_id")
                if action == "salvar_linha" and comprovante_id_linha:
                    atualizar_status_comprovante(
                        int(comprovante_id_linha),
                        request.form.get("status"),
                        request.form.get("observacao_admin"),
                    )
                    flash("Pessoa e status salvos com sucesso.", "success")
                else:
                    flash("Pessoa salva no cadastro com perfil filhe.", "success")
                return redirect(url_for("admin.financeiro", mes=request.args.get("mes", mes_atual()), tipo=request.args.get("tipo", "Todos"), status=request.args.get("status", "Todos")))

            comprovante_id = request.form.get("comprovante_id")
            if not comprovante_id:
                raise ValueError("Esta pessoa ainda não possui movimentação no portal para atualizar.")

            atualizar_status_comprovante(
                int(comprovante_id),
                request.form.get("status"),
                request.form.get("observacao_admin"),
            )
            flash("Status atualizado com sucesso.", "success")
            return redirect(url_for("admin.financeiro", mes=request.args.get("mes", mes_atual()), tipo=request.args.get("tipo", "Todos"), status=request.args.get("status", "Todos")))
        except Exception as exc:
            flash(str(exc), "danger")

    mes = request.args.get("mes", mes_atual())
    df = montar_conciliacao(mes)
    tipo = request.args.get("tipo", "Todos")
    status = request.args.get("status", "Todos")
    sort = request.args.get("sort", "nome")
    direction = request.args.get("direction", "asc")
    filtered = df.copy() if df is not None else pd.DataFrame()
    if not filtered.empty and tipo != "Todos":
        filtered = filtered[filtered["tipo_label"].astype(str) == tipo]
    if not filtered.empty and status != "Todos":
        filtered = filtered[filtered["status_label"].astype(str) == status]
    sort_map = {
        "nome": "nome",
        "cpf": "cpf",
        "telefone": "telefone",
        "email": "email",
        "nascimento": "data_nascimento",
        "mes": "mes_referencia",
        "tipo": "tipo_label",
        "valor": "valor_informado",
        "status": "status_label",
    }
    sort_col = sort_map.get(sort, "nome")
    if not filtered.empty and sort_col in filtered.columns:
        filtered = filtered.sort_values(
            by=sort_col,
            ascending=(direction != "desc"),
            na_position="last",
            key=lambda col: col.astype(str).str.lower() if col.dtype == object else col,
        )
    tipos = ["Todos"] + sorted(df["tipo_label"].dropna().astype(str).unique().tolist()) if df is not None and not df.empty else ["Todos"]
    status_options = ["Todos", "Pendente", "Em Análise", "Aprovado", "Reprovado"]
    resumo = resumo_financeiro(filtered)
    return render_template(
        "admin/financeiro.html",
        rows=df_records(filtered),
        tipos=tipos,
        status_options=status_options,
        tipo=tipo,
        status=status,
        sort=sort,
        direction=direction,
        mes=mes,
        meses=meses_disponiveis(),
        resumo=resumo,
        valor_total_formatado=format_brl_value(resumo["valor_total"]),
        valor_pago_formatado=format_brl_value(resumo["valor_pago"]),
        valor_pendente_formatado=format_brl_value(resumo["valor_pendente"]),
    )


@bp.get("/financeiro/export")
@admin_required
def financeiro_export():
    df = montar_conciliacao(request.args.get("mes", mes_atual()))
    tipo = request.args.get("tipo", "Todos")
    status = request.args.get("status", "Todos")
    filtered = df.copy() if df is not None else pd.DataFrame()
    if not filtered.empty and tipo != "Todos":
        filtered = filtered[filtered["tipo_label"].astype(str) == tipo]
    if not filtered.empty and status != "Todos":
        filtered = filtered[filtered["status_label"].astype(str) == status]
    return excel_response(filtered, "financeiro_conciliacao.xlsx")


@bp.get("/financeiro-dashboard")
@admin_required
def financeiro_dashboard():
    df = listar_movimentacoes_financeiras()
    pessoas = montar_conciliacao(request.args.get("mes", mes_atual()))

    sazonalidade = request.args.get("sazonalidade", "Mês")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    tipo = request.args.get("tipo", "Todos")
    status = request.args.get("status", "Todos")
    nome = (request.args.get("nome") or "").strip()

    filtered = df.copy() if df is not None else pd.DataFrame()
    if not filtered.empty:
        filtered["created_at_dt"] = pd.to_datetime(filtered["created_at"], errors="coerce")
        if data_inicio:
            filtered = filtered[filtered["created_at_dt"] >= pd.to_datetime(data_inicio)]
        if data_fim:
            filtered = filtered[filtered["created_at_dt"] <= pd.to_datetime(data_fim) + pd.Timedelta(days=1)]
        if tipo != "Todos":
            filtered = filtered[filtered["tipo_label"] == tipo]
        if status != "Todos":
            filtered = filtered[filtered["status_label"] == status]
        if nome:
            filtered = filtered[filtered["nome"].astype(str).str.contains(nome, case=False, na=False)]

    resumo = resumo_financeiro(filtered)

    meses = meses_disponiveis()
    chart_rows = []
    pessoas_total = len(pessoas) if pessoas is not None else 0
    for mes_ref in sorted(meses, key=lambda item: (item[-4:], item[:2])):
        conc = montar_conciliacao(mes_ref)
        em_dia = int(conc["status_label"].astype(str).eq("Aprovado").sum()) if not conc.empty else 0
        chart_rows.append({"mes": mes_ref, "em_dia": em_dia, "inadimplentes": max(pessoas_total - em_dia, 0)})

    meses_pagas = []
    meses_atrasadas = []
    if pessoas is not None and not pessoas.empty:
        for _, pessoa in pessoas.iterrows():
            nome_pessoa = pessoa.get("nome")
            pessoa_mov = df[df["nome_norm"] == pessoa.get("nome_norm")] if df is not None and not df.empty else pd.DataFrame()
            em_dia = int(pessoa_mov["status_label"].astype(str).eq("Aprovado").sum()) if not pessoa_mov.empty else 0
            devidas = max(len(meses) - em_dia, 0)
            row = {
                "nome": nome_pessoa,
                "email": pessoa.get("email"),
                "telefone": pessoa.get("telefone"),
                "mensalidades_em_dia": em_dia,
                "mensalidades_pendentes": devidas,
            }
            if devidas == 0:
                meses_pagas.append(row)
            else:
                meses_atrasadas.append(row)

    meses_atrasadas = sorted(meses_atrasadas, key=lambda item: item["mensalidades_pendentes"], reverse=True)
    page_size = 15
    pagina_em_dia = max(int(request.args.get("pagina_em_dia", 1) or 1), 1)
    pagina_inadimplentes = max(int(request.args.get("pagina_inadimplentes", 1) or 1), 1)
    total_paginas_em_dia = max((len(meses_pagas) + page_size - 1) // page_size, 1)
    total_paginas_inadimplentes = max((len(meses_atrasadas) + page_size - 1) // page_size, 1)
    pagina_em_dia = min(pagina_em_dia, total_paginas_em_dia)
    pagina_inadimplentes = min(pagina_inadimplentes, total_paginas_inadimplentes)
    pagas_paginadas = meses_pagas[(pagina_em_dia - 1) * page_size:pagina_em_dia * page_size]
    atrasadas_paginadas = meses_atrasadas[(pagina_inadimplentes - 1) * page_size:pagina_inadimplentes * page_size]
    dashboard_counts = {
        "em_dia": len(meses_pagas),
        "inadimplentes": len(meses_atrasadas),
    }

    return render_template(
        "admin/financeiro_dashboard.html",
        resumo=resumo,
        valor_total_formatado=format_brl_value(resumo["valor_total"]),
        valor_pago_formatado=format_brl_value(resumo["valor_pago"]),
        valor_pendente_formatado=format_brl_value(resumo["valor_pendente"]),
        sazonalidade=sazonalidade,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo=tipo,
        status=status,
        nome=nome,
        tipos=["Todos"] + list(label_tipo(t) for t in ["mensalidade", "contribuicao_voluntaria", "pac_contribuicao"]),
        status_options=["Todos", "Pendente", "Em Análise", "Aprovado", "Reprovado"],
        chart_rows=chart_rows,
        pagas=pagas_paginadas,
        atrasadas=atrasadas_paginadas,
        dashboard_counts=dashboard_counts,
        pagina_em_dia=pagina_em_dia,
        pagina_inadimplentes=pagina_inadimplentes,
        total_paginas_em_dia=total_paginas_em_dia,
        total_paginas_inadimplentes=total_paginas_inadimplentes,
    )


@bp.route("/portal-usuarios", methods=["GET", "POST"])
@admin_required
def portal_usuarios():
    if request.method == "POST":
        try:
            atualizar_status_usuario_portal(
                user_id=int(request.form.get("user_id")),
                status=request.form.get("status"),
                observacao_admin=request.form.get("observacao_admin"),
                admin_email=session.get("admin", {}).get("email"),
            )
            flash("Status do usuário atualizado com sucesso.", "success")
            return redirect(url_for("admin.portal_usuarios"))
        except Exception as exc:
            flash(str(exc), "danger")

    df = listar_solicitacoes_portal()
    return render_template(
        "admin/portal_usuarios.html",
        rows=df_records(df),
        total=0 if df is None else len(df),
    )


@bp.get("/portal-usuarios/export")
@admin_required
def portal_usuarios_export():
    return excel_response(listar_solicitacoes_portal(), "portal_usuarios.xlsx")


@bp.get("/comprovantes")
@admin_required
def comprovantes_redirect():
    return redirect(url_for("admin.financeiro"))


@bp.get("/financeiro/download/<int:comprovante_id>")
@bp.get("/comprovantes/download/<int:comprovante_id>")
@admin_required
def comprovante_download(comprovante_id: int):
    df = listar_comprovantes()
    if df is None or df.empty or "id" not in df:
        flash("Comprovante não encontrado.", "danger")
        return redirect(url_for("admin.financeiro"))
    row = df[df["id"] == comprovante_id]
    if row.empty:
        flash("Comprovante não encontrado.", "danger")
        return redirect(url_for("admin.financeiro"))
    arquivo = normalize_file_path(row.iloc[0].get("arquivo_path"), Path(BASE_DIR))
    if not arquivo:
        flash("Arquivo do comprovante não encontrado no servidor.", "danger")
        return redirect(url_for("admin.financeiro"))
    return send_file(arquivo, as_attachment=True)


@bp.get("/limpeza")
@admin_required
def limpeza():
    return render_template("admin/status.html", title="Limpeza", message="Conteúdo em desenvolvimento")


@bp.get("/limpeza/export")
@admin_required
def limpeza_export():
    return excel_response(listar_limpeza(), "limpeza.xlsx")


@bp.get("/faltas")
@admin_required
def faltas():
    df = listar_faltas()
    base = df.copy() if df is not None else pd.DataFrame()
    sazonalidade = request.args.get("sazonalidade", "Dia")
    if sazonalidade not in {"Dia", "Mês", "Ano"}:
        sazonalidade = "Dia"
    por_data = []
    por_pessoa = []
    if not base.empty:
        base["data_dt"] = pd.to_datetime(base["data_registro"], errors="coerce")
        if sazonalidade == "Ano":
            base["data"] = base["data_dt"].dt.strftime("%Y")
        elif sazonalidade == "Mês":
            base["data"] = base["data_dt"].dt.strftime("%m/%Y")
        else:
            base["data"] = base["data_dt"].dt.strftime("%Y-%m-%d")
        por_data = (
            base.groupby("data", as_index=False)
            .size()
            .rename(columns={"size": "quantidade"})
            .sort_values("data")
            .to_dict(orient="records")
        )
        pessoa_col = "quem_escolhe" if "quem_escolhe" in base.columns else base.columns[0]
        por_pessoa = (
            base.groupby(pessoa_col, as_index=False)
            .size()
            .rename(columns={pessoa_col: "pessoa", "size": "quantidade"})
            .sort_values("quantidade", ascending=False)
            .to_dict(orient="records")
        )
    page_size = 15
    pagina = max(int(request.args.get("pagina", 1) or 1), 1)
    total_paginas = max((len(por_pessoa) + page_size - 1) // page_size, 1)
    pagina = min(pagina, total_paginas)
    por_pessoa_paginado = por_pessoa[(pagina - 1) * page_size:pagina * page_size]
    return render_template(
        "admin/faltas.html",
        total=0 if df is None else len(df),
        por_data=por_data,
        por_pessoa=por_pessoa_paginado,
        sazonalidade=sazonalidade,
        pagina=pagina,
        total_paginas=total_paginas,
        export_url=url_for("admin.faltas_export"),
    )


@bp.get("/faltas/export")
@admin_required
def faltas_export():
    return excel_response(listar_faltas(), "faltas.xlsx")
