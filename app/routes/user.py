from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from config.settings import CESTA_BASICA_PAC_VALOR, PIX_CUSLE_CHAVE, PIX_CUSLE_NOME
from services.financeiro_service import (
    parse_brl_value,
    registrar_comprovante_mensalidade,
    registrar_comprovante_pac_contribuicao,
)
from services.conteudo_service import obter_conteudo
from services.cursos_service import (
    PERFIL_LABELS,
    catalogo_para_ui,
    listar_inscricoes_cadastro,
    normalizar_perfil,
    registrar_cursos,
)
from services.pac_service import (
    cadastrar_familia_pac,
    listar_criancas_disponiveis_apadrinhamento,
    listar_filhes_santo_apadrinhamento,
    registrar_apadrinhamento_pac,
)
from services.assinatura_service import criar_ou_obter_envelope
from services.cadastro_service import buscar_cadastro_por_cpf, buscar_cadastro_por_email
from services.portal_auth_service import (
    autenticar_usuario_portal,
    buscar_status_portal,
    mensagem_status_portal,
    registrar_usuario_portal,
)
from app.routes.helpers import df_records, portal_required

bp = Blueprint("user", __name__)

SEXO = ["", "Feminino", "Masculino", "Outro", "Prefiro não informar"]
ETNIAS = ["", "Preto", "Branco", "Pardo", "Amarelo"]

FINANCEIRO = {
    "mensalidade": {
        "title": "Mensalidade / Contribuição",
        "subtitle": "Envie o comprovante da mensalidade e, se desejar, informe contribuição voluntária e cesta básica PAC.",
        "service": registrar_comprovante_mensalidade,
        "show_month": True,
        "show_extra_options": True,
    },
    "pac-contribuicao": {
        "title": "Contribuição PAC",
        "subtitle": "Envie uma contribuição vinculada ao Programa Acolhe CUSLE.",
        "service": registrar_comprovante_pac_contribuicao,
        "show_month": False,
        "show_extra_options": False,
    },
}


def _format_decimal_br(value: float) -> str:
    return f"{float(value):.2f}".replace(".", ",")


def _opcoes_mes_referencia() -> list[dict[str, str]]:
    meses = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]
    ano = 2026

    return [
        {"value": f"{mes:02d}/{ano}", "label": f"{meses[mes - 1]}/{ano}"}
        for mes in range(1, 13)
    ]


def _calcular_total_mensalidade(form) -> tuple[str, str | None]:
    valor_base = parse_brl_value(form.get("valor"))
    detalhes = [f"Mensalidade base: R$ {_format_decimal_br(valor_base)}"]

    total = valor_base

    if form.get("tem_contribuicao_voluntaria") == "on":
        valor_voluntario = parse_brl_value(form.get("valor_contribuicao_voluntaria"))
        total += valor_voluntario
        detalhes.append(f"Contribuição voluntária: R$ {_format_decimal_br(valor_voluntario)}")

    if form.get("tem_cesta_basica") == "on":
        qtd_cestas = int(form.get("qtd_cestas") or 0)
        if qtd_cestas <= 0:
            raise ValueError("Informe a quantidade de cestas básicas PAC.")
        valor_cesta = float(CESTA_BASICA_PAC_VALOR or 0)
        total_cestas = qtd_cestas * valor_cesta
        total += total_cestas
        detalhes.append(f"Cesta básica PAC: {qtd_cestas} unidade(s) x R$ {_format_decimal_br(valor_cesta)} = R$ {_format_decimal_br(total_cestas)}")

    detalhes.append(f"Total informado: R$ {_format_decimal_br(total)}")
    return _format_decimal_br(total), " | ".join(detalhes)


def _portal_user() -> dict:
    return session.get("portal_user") or {}


def _portal_cadastro() -> dict:
    usuario = _portal_user()
    cadastro = buscar_cadastro_por_cpf(usuario.get("cpf"))
    if cadastro:
        return cadastro
    return buscar_cadastro_por_email(usuario.get("email")) or {}


def _cadastro_form_data() -> dict:
    cadastro = _portal_cadastro()
    data = dict(cadastro)
    data_nascimento = data.get("data_nascimento")
    data["data_nascimento_input"] = data_nascimento.isoformat() if hasattr(data_nascimento, "isoformat") else (data_nascimento or "")
    data["menor_idade_value"] = "" if data.get("menor_idade") is None else ("sim" if data.get("menor_idade") else "nao")
    data["perfil"] = normalizar_perfil(data.get("perfil"))
    return data


@bp.get("/")
def landing():
    return render_template("user/landing.html")


@bp.get("/portal")
@portal_required
def home():
    usuario = _portal_user()
    if usuario.get("is_admin_pac"):
        cards = [
            {"title": "PAC - Programa Acolhe CUSLE", "desc": "Cadastro assistido, apadrinhamento e contribuição.", "url": url_for("user.pac_menu")},
            {"title": "Admin PAC", "desc": "Painel administrativo exclusivo do PAC.", "url": url_for("admin_pac.dashboard")},
        ]
        return render_template("user/home.html", title="Portal CUSLE", subtitle=None, cards=cards, is_home=True)

    cards = [
        {"title": "Filho de Santo", "desc": "Mensalidade, limpeza e justificativas.", "url": url_for("user.filho_santo")},
        {"title": "PAC - Programa Acolhe CUSLE", "desc": "Cadastro assistido, apadrinhamento e contribuição.", "url": url_for("user.pac_menu")},
        {"title": "Medicina", "desc": "Conteúdo reservado para orientações.", "url": url_for("user.placeholder", area="medicina")},
        {"title": "Assistência", "desc": "Frentes assistenciais e apoio.", "url": url_for("user.placeholder", area="assistencia")},
        {"title": "Cursos e Capacitações", "desc": "Inscrição em cursos e capacitações da CUSLE.", "url": url_for("user.cursos")},
    ]
    return render_template("user/home.html", title="Portal CUSLE", subtitle=None, cards=cards, is_home=True)


@bp.route("/portal/login", methods=["GET", "POST"])
def portal_login():
    if request.method == "POST":
        usuario = autenticar_usuario_portal(request.form.get("email"), request.form.get("senha"))
        if usuario:
            session["portal_logado"] = True
            session["portal_user"] = usuario
            if usuario.get("is_admin"):
                session["admin_logado"] = True
                session["admin"] = {"nome": usuario.get("nome"), "email": usuario.get("email")}
            if usuario.get("is_admin_pac"):
                session["admin_pac_logado"] = True
                session["admin_pac"] = {"nome": usuario.get("nome"), "email": usuario.get("email"), "role": "admin_pac"}
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("user.home"))

        status = buscar_status_portal(email=request.form.get("email"))
        flash(mensagem_status_portal(status), "warning")
    return render_template("user/portal_login.html")


@bp.route("/portal/registrar", methods=["GET", "POST"])
def portal_register():
    status_info = None
    status_message = None
    if request.method == "POST":
        try:
            registrar_usuario_portal(
                email=request.form.get("email"),
                cpf=request.form.get("cpf"),
                senha=request.form.get("senha"),
                confirmar_senha=request.form.get("confirmar_senha"),
            )
            status_info = buscar_status_portal(email=request.form.get("email"), cpf=request.form.get("cpf"))
            status_message = mensagem_status_portal(status_info)
            flash("Solicitação enviada para aprovação administrativa.", "success")
        except Exception as exc:
            flash(str(exc), "danger")
    return render_template("user/portal_register.html", status_info=status_info, status_message=status_message)


@bp.route("/portal/status", methods=["GET", "POST"])
def portal_status():
    status_info = None
    status_message = None
    if request.method == "POST":
        status_info = buscar_status_portal(email=request.form.get("email"), cpf=request.form.get("cpf"))
        status_message = mensagem_status_portal(status_info)
    return render_template("user/portal_status.html", status_info=status_info, status_message=status_message)


@bp.get("/portal/logout")
def portal_logout():
    session.pop("portal_logado", None)
    session.pop("portal_user", None)
    flash("Acesso do portal encerrado.", "success")
    return redirect(url_for("user.portal_login"))


@bp.get("/filho-santo")
@portal_required
def filho_santo():
    cards = [
        {"title": "Mensalidade / Contribuição", "desc": "Enviar comprovante mensal, contribuição voluntária e cesta básica PAC.", "url": url_for("user.financeiro", tipo="mensalidade")},
        {"title": "Limpeza", "desc": "Registrar participação na limpeza.", "url": url_for("user.limpeza")},
        {"title": "Faltas", "desc": "Acesso ao sistema externo de justificativa.", "url": "https://lista-cambones.onrender.com/faltas", "external": True},
    ]
    return render_template("user/home.html", title="Filho de Santo", subtitle="Escolha uma opção", cards=cards)


@bp.route("/financeiro/<tipo>", methods=["GET", "POST"])
@portal_required
def financeiro(tipo: str):
    cfg = FINANCEIRO.get(tipo)
    if not cfg:
        flash("Tipo de comprovante inválido.", "danger")
        return redirect(url_for("user.home"))
    if request.method == "POST":
        try:
            usuario = _portal_user()
            cadastro = _portal_cadastro()
            if usuario and not usuario.get("is_admin") and not cadastro:
                raise ValueError("Nao encontramos seu cadastro pelo CPF ou e-mail do login. Entre em contato com a administracao para atualizar seu cadastro.")

            nome = cadastro.get("nome") or request.form.get("nome")
            cpf = cadastro.get("cpf") or request.form.get("cpf")
            telefone = cadastro.get("telefone") or request.form.get("telefone")
            valor = request.form.get("valor")
            justificativa = request.form.get("justificativa")
            arquivo = request.files.get("comprovante")

            if cfg["show_month"]:
                valor_total, detalhes = _calcular_total_mensalidade(request.form)
                observacoes = "\n".join([x for x in [justificativa, detalhes] if x])
                cfg["service"](nome, cpf, telefone, request.form.get("mes_referencia"), valor_total, observacoes, arquivo)
            else:
                cfg["service"](nome, cpf, telefone, valor, justificativa, arquivo)
            flash("Comprovante enviado com sucesso.", "success")
            return redirect(url_for("user.financeiro", tipo=tipo))
        except Exception as exc:
            flash(str(exc), "danger")
    return render_template(
        "user/financeiro_form.html",
        cfg=cfg,
        pix_chave=PIX_CUSLE_CHAVE,
        pix_nome=PIX_CUSLE_NOME,
        cesta_basica_valor=float(CESTA_BASICA_PAC_VALOR or 0),
        meses_referencia=_opcoes_mes_referencia(),
        cadastro_user=_portal_cadastro(),
    )


@bp.route("/cursos", methods=["GET", "POST"])
@portal_required
def cursos():
    cadastro = _cadastro_form_data()
    usuario = _portal_user()
    if usuario and not usuario.get("is_admin") and not cadastro:
        flash("Nao encontramos seu cadastro pelo CPF ou e-mail do login. Entre em contato com a administracao para atualizar seu cadastro.", "danger")
        return redirect(url_for("user.home"))

    if request.method == "POST":
        try:
            registrar_cursos(cadastro, request.form)
            flash("Inscrição registrada com sucesso.", "success")
            return redirect(url_for("user.cursos_sucesso"))
        except Exception as exc:
            flash(str(exc), "danger")

    inscricoes = listar_inscricoes_cadastro(cadastro["id"]) if cadastro.get("id") else []
    return render_template(
        "user/cursos_form.html",
        title="Cursos e Capacitações",
        subtitle="Escolha os cursos disponíveis para seu perfil.",
        cadastro_user=cadastro,
        catalog=catalogo_para_ui(),
        perfil_labels=PERFIL_LABELS,
        inscricoes=inscricoes,
    )


@bp.get("/cursos/sucesso")
@portal_required
def cursos_sucesso():
    cadastro = _cadastro_form_data()
    if not cadastro.get("id"):
        flash("Cadastro não encontrado.", "danger")
        return redirect(url_for("user.home"))

    return render_template(
        "user/cursos_sucesso.html",
        title="Inscrição registrada",
        subtitle="Cursos e capacitações CUSLE",
        cadastro_user=cadastro,
        cursos=listar_inscricoes_cadastro(cadastro["id"]),
        perfil_labels=PERFIL_LABELS,
    )


@bp.route("/limpeza", methods=["GET", "POST"])
@portal_required
def limpeza():
    return render_template("user/placeholder.html", title="Limpeza")


@bp.get("/pac")
def pac_menu():
    cards = [
        {"title": "Cadastro Assistido", "desc": "Cadastro de pessoa assistida e filhos.", "url": url_for("user.pac_cadastro")},
        {"title": "Apadrinhamento", "desc": "Escolher criança disponível para apadrinhar.", "url": url_for("user.pac_apadrinhamento")},
        {"title": "Contribuição PAC", "desc": "Enviar comprovante de contribuição.", "url": url_for("user.financeiro", tipo="pac-contribuicao")},
    ]
    return render_template("user/home.html", title="PAC - Programa Acolhe CUSLE", subtitle="Escolha uma frente de atendimento", cards=cards)


@bp.route("/pac/cadastro", methods=["GET", "POST"])
def pac_cadastro():
    assinatura_url = None
    if request.method == "POST":
        try:
            qtd_filhos = int(request.form.get("qtd_filhos") or 0)
            responsavel = {
                "nome": request.form.get("nome"),
                "nome_social": request.form.get("nome_social"),
                "cpf": request.form.get("cpf"),
                "email": request.form.get("email"),
                "telefone": request.form.get("telefone"),
                "data_nascimento": request.form.get("data_nascimento"),
                "sexo": request.form.get("sexo"),
                "etnia": request.form.get("etnia"),
                "possui_deficiencia": request.form.get("possui_deficiencia") == "Sim",
                "descricao_deficiencia": request.form.get("descricao_deficiencia"),
                "dados_compartilhamento": request.form.get("dados_compartilhamento") == "on",
                "endereco_completo": request.form.get("endereco_completo"),
                "estado_civil": request.form.get("estado_civil"),
                "com_quem_mora": request.form.get("com_quem_mora"),
                "situacao_trabalho": request.form.get("situacao_trabalho"),
                "renda_mensal": request.form.get("renda_mensal"),
                "renda_familiar": request.form.get("renda_familiar"),
                "cadastro_unico": request.form.get("cadastro_unico"),
                "beneficios": ", ".join(request.form.getlist("beneficios")),
                "problema_saude": request.form.get("problema_saude"),
                "medicacao_continua": request.form.get("medicacao_continua"),
                "acompanhamento_psicologico": request.form.get("acompanhamento_psicologico"),
                "alergia": request.form.get("alergia"),
                "filho_saude_alergia": request.form.get("filho_saude_alergia"),
                "filho_medicacao": request.form.get("filho_medicacao"),
                "refeicoes_dia": request.form.get("refeicoes_dia"),
                "moradia": request.form.get("moradia"),
                "saneamento_basico": request.form.get("saneamento_basico"),
                "apoio_interesse": ", ".join(request.form.getlist("apoio_interesse")),
                "dificuldades": request.form.get("dificuldades"),
                "pode_oficina": request.form.get("pode_oficina"),
                "rg_cpf": request.form.get("rg_cpf"),
                "sugestao_pac": request.form.get("sugestao_pac"),
            }
            filhos = []
            for i in range(qtd_filhos):
                filhos.append({
                    "nome": request.form.get(f"filho_nome_{i}"),
                    "documento": request.form.get(f"filho_documento_{i}"),
                    "data_nascimento": request.form.get(f"filho_data_nascimento_{i}"),
                    "sexo": request.form.get(f"filho_sexo_{i}"),
                    "etnia": request.form.get(f"filho_etnia_{i}"),
                    "possui_deficiencia": request.form.get(f"filho_possui_deficiencia_{i}") == "Sim",
                    "descricao_deficiencia": request.form.get(f"filho_descricao_deficiencia_{i}"),
                    "problema_saude": request.form.get(f"filho_problema_saude_{i}"),
                    "alergia": request.form.get(f"filho_alergia_{i}"),
                    "medicacao_continua": request.form.get(f"filho_medicacao_continua_{i}"),
                })
            resultado = cadastrar_familia_pac(responsavel=responsavel, filhos=filhos)
            envelope = criar_ou_obter_envelope("pac_batch", int(resultado["responsavel"]["cadastro"]["id"]))
            assinatura_url = envelope.get("sign_url")
            flash("Cadastro PAC realizado com sucesso.", "success")
        except Exception as exc:
            flash(str(exc), "danger")
    return render_template(
        "user/pac_cadastro.html",
        sexo=SEXO,
        etnias=ETNIAS,
        assinatura_url=assinatura_url,
        today=date.today().isoformat(),
    )


@bp.route("/pac/apadrinhamento", methods=["GET", "POST"])
def pac_apadrinhamento():
    erro_banco = None
    padrinhos = []
    criancas = []

    try:
        padrinhos_df = listar_filhes_santo_apadrinhamento()
        criancas_df = listar_criancas_disponiveis_apadrinhamento()
        padrinhos = df_records(padrinhos_df)
        criancas = df_records(criancas_df)
    except Exception as exc:
        erro_banco = str(exc)
        flash("Não foi possível carregar os dados de apadrinhamento. Verifique a conexão com o banco e a estrutura PAC.", "danger")

    if request.method == "POST" and not erro_banco:
        try:
            registrar_apadrinhamento_pac(
                int(request.form.get("padrinho_id")),
                int(request.form.get("crianca_id")),
            )
            flash("Apadrinhamento registrado com sucesso.", "success")
            return redirect(url_for("user.pac_apadrinhamento"))
        except Exception as exc:
            flash(str(exc), "danger")

    return render_template(
        "user/pac_apadrinhamento.html",
        padrinhos=padrinhos,
        criancas=criancas,
        erro_banco=erro_banco,
    )


@bp.get("/area/<area>")
def placeholder(area: str):
    titles = {"medicina": "Medicina", "assistencia": "Assistência", "cursos": "Cursos"}
    if area in {"medicina", "assistencia"}:
        conteudo = obter_conteudo(f"{area}_menu")
        return render_template(
            "user/conteudo.html",
            title=conteudo["titulo"],
            conteudo=conteudo["conteudo"],
            destaque=conteudo.get("destaque"),
        )
    return render_template("user/placeholder.html", title=titles.get(area, area.title()))
