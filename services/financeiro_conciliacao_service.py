from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import unicodedata

import pandas as pd

from config.settings import BASE_DIR
from db.database import execute_command, execute_returning, run_query
from services.cadastro_service import only_digits


UPLOAD_DIR = Path(BASE_DIR) / "uploads" / "financeiro"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ROOT_PESSOAS_PATH = Path(BASE_DIR) / "lista_pessoas.xlsx"
PESSOAS_PATH = UPLOAD_DIR / "pessoas_conciliacao.xlsx"
PESSOAS_CSV_PATH = UPLOAD_DIR / "pessoas_conciliacao.csv"

TIPOS_FINANCEIROS = {
    "mensalidade": "Mensalidade",
    "contribuicao_voluntaria": "Voluntária",
    "pac_contribuicao": "Contribuição PAC",
}

STATUS_LABELS = {
    "pendente": "Pendente",
    "em_analise": "Em Análise",
    "pago": "Aprovado",
    "aprovado": "Aprovado",
    "reprovado": "Reprovado",
    "recusado": "Reprovado",
}

PAID_STATUSES = {"pago", "aprovado", "aprovados", "paid"}
REJECTED_STATUSES = {"reprovado", "recusado", "rejeitado"}


def mes_atual() -> str:
    hoje = date.today()
    return f"{hoje.month:02d}/{hoje.year}"


def normalizar_nome(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().strip()
    return re.sub(r"\s+", " ", normalized)


def label_status(status: str | None, has_movimento: bool = False) -> str:
    status_norm = str(status or "").strip().lower()
    if not status_norm and not has_movimento:
        return "Pendente"
    if status_norm in PAID_STATUSES:
        return "Aprovado"
    if status_norm in REJECTED_STATUSES:
        return "Reprovado"
    if has_movimento:
        return "Em Análise"
    return STATUS_LABELS.get(status_norm, status_norm.replace("_", " ").title() or "Pendente")


def label_tipo(tipo: str | None) -> str:
    tipo_norm = str(tipo or "").strip().lower()
    return TIPOS_FINANCEIROS.get(tipo_norm, tipo_norm.replace("_", " ").title() or "-")


def limpar_id(value):
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: str | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def _clean_email(value: str | None) -> str | None:
    value = _clean_text(value)
    return value.lower() if value else None


def _slug(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "pessoa"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", ".", text.lower()).strip(".")
    return text or "pessoa"


def _email_ou_fallback(email: str | None, nome: str) -> str:
    return _clean_email(email) or f"sem-email+{_slug(nome)}@cusle.local"


def _clean_date(value: str | None) -> str | None:
    value = _clean_text(value)
    return value or None


def _format_date_for_input(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)[:10]


def ensure_cadastro_conciliacao_ready() -> None:
    execute_command("ALTER TABLE cadastro.cadastro ALTER COLUMN cpf DROP NOT NULL;")
    execute_command("ALTER TABLE cadastro.cadastro ALTER COLUMN telefone DROP NOT NULL;")
    execute_command("ALTER TABLE cadastro.cadastro ALTER COLUMN data_nascimento DROP NOT NULL;")


def listar_cadastro_filhes() -> pd.DataFrame:
    return run_query(
        """
        SELECT
            id AS cadastro_id,
            nome,
            cpf,
            telefone,
            email,
            data_nascimento,
            perfil
        FROM cadastro.cadastro
        WHERE LOWER(COALESCE(perfil, '')) IN ('filhe', 'filhes')
        ORDER BY nome;
        """
    )


def listar_cadastro_todos() -> pd.DataFrame:
    return run_query(
        """
        SELECT
            id AS cadastro_id,
            nome,
            cpf,
            telefone,
            email,
            data_nascimento,
            perfil
        FROM cadastro.cadastro;
        """
    )


def marcar_cadastro_como_filhe(cadastro_id: int, nome: str | None = None) -> dict | None:
    return execute_returning(
        """
        UPDATE cadastro.cadastro
        SET
            nome = COALESCE(:nome, nome),
            perfil = 'filhe'
        WHERE id = :cadastro_id
        RETURNING id, nome, cpf, telefone, email, data_nascimento, perfil;
        """,
        {
            "cadastro_id": cadastro_id,
            "nome": _clean_text(nome),
        },
    )


def carregar_pessoas_base() -> pd.DataFrame:
    return listar_cadastro_filhes()


def carregar_planilha_pessoas() -> pd.DataFrame:
    if ROOT_PESSOAS_PATH.exists():
        return pd.read_excel(ROOT_PESSOAS_PATH)
    if PESSOAS_PATH.exists():
        return pd.read_excel(PESSOAS_PATH)
    if PESSOAS_CSV_PATH.exists():
        return pd.read_csv(PESSOAS_CSV_PATH, sep=None, engine="python")
    return pd.DataFrame()


def salvar_planilha_pessoas(uploaded_file) -> None:
    filename = (getattr(uploaded_file, "filename", "") or "").lower()
    if not filename:
        raise ValueError("Selecione uma planilha de pessoas.")

    suffix = Path(filename).suffix
    if suffix not in {".xlsx", ".xls", ".csv", ".tsv"}:
        raise ValueError("Envie uma planilha .xlsx, .xls, .csv ou .tsv.")

    target = PESSOAS_CSV_PATH if suffix in {".csv", ".tsv"} else PESSOAS_PATH
    other = PESSOAS_PATH if target == PESSOAS_CSV_PATH else PESSOAS_CSV_PATH
    uploaded_file.save(target)
    if other.exists():
        other.unlink()


def _detectar_coluna_nome(df: pd.DataFrame) -> str:
    normalized_cols = {
        normalizar_nome(col).replace(" ", "_"): col
        for col in df.columns
    }
    for candidate in ("nome", "nome_completo", "pessoa", "filho", "filhe", "nome_da_pessoa"):
        if candidate in normalized_cols:
            return normalized_cols[candidate]
    raise ValueError("Não encontrei uma coluna de nome na planilha. Use uma coluna chamada Nome.")


def _detectar_coluna_opcional(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    normalized_cols = {
        normalizar_nome(col).replace(" ", "_"): col
        for col in df.columns
    }
    for candidate in candidates:
        if candidate in normalized_cols:
            return normalized_cols[candidate]
    return None


def _preparar_pessoas(df_planilha: pd.DataFrame) -> pd.DataFrame:
    cadastro = listar_cadastro_filhes()

    if df_planilha is None or df_planilha.empty:
        pessoas = cadastro.copy()
        if "nome" not in pessoas:
            return pd.DataFrame(columns=["nome", "nome_norm", "cpf", "telefone", "email", "data_nascimento", "cadastro_id"])
    elif "cadastro_id" in df_planilha.columns:
        pessoas = df_planilha.copy()
    else:
        nome_col = _detectar_coluna_nome(df_planilha)
        pessoas = pd.DataFrame({"nome": df_planilha[nome_col].astype(str).str.strip()})
        pessoas = pessoas[pessoas["nome"].ne("") & pessoas["nome"].str.lower().ne("nan")]

    pessoas["nome_norm"] = pessoas["nome"].apply(normalizar_nome)
    if "data_nascimento" in pessoas.columns:
        pessoas["data_nascimento"] = pessoas["data_nascimento"].apply(_format_date_for_input)
    if "cadastro_id" in pessoas.columns and {"cpf", "telefone", "email"}.issubset(set(pessoas.columns)):
        return pessoas.drop_duplicates(subset=["nome_norm"]).sort_values("nome")

    cadastro = cadastro.copy() if cadastro is not None else pd.DataFrame()
    if not cadastro.empty:
        cadastro["nome_norm"] = cadastro["nome"].apply(normalizar_nome)
        pessoas = pessoas.merge(
            cadastro[["nome_norm", "cadastro_id", "cpf", "telefone", "email", "data_nascimento", "perfil"]],
            on="nome_norm",
            how="left",
            suffixes=("", "_cadastro"),
        )
    else:
        for col in ["cadastro_id", "cpf", "telefone", "email", "data_nascimento", "perfil"]:
            pessoas[col] = None

    return pessoas.drop_duplicates(subset=["nome_norm"]).sort_values("nome")


def salvar_pessoa_filhe(
    cadastro_id: str | int | None = None,
    nome: str | None = None,
    cpf: str | None = None,
    telefone: str | None = None,
    email: str | None = None,
    data_nascimento: str | None = None,
) -> dict | None:
    nome_limpo = _clean_text(nome)
    if not nome_limpo:
        raise ValueError("Nome é obrigatório para salvar a pessoa.")

    ensure_cadastro_conciliacao_ready()

    cadastro_id_limpo = limpar_id(cadastro_id)
    cpf_limpo = only_digits(cpf)
    telefone_limpo = only_digits(telefone)
    email_limpo = _email_ou_fallback(email, nome_limpo)
    data_nascimento_limpa = _clean_date(data_nascimento)

    if not cadastro_id_limpo:
        candidatos = listar_cadastro_todos()
        if candidatos is not None and not candidatos.empty:
            if cpf_limpo:
                por_cpf = candidatos[candidatos["cpf"].astype(str) == cpf_limpo]
                if not por_cpf.empty:
                    cadastro_id_limpo = limpar_id(por_cpf.iloc[0].get("cadastro_id"))
            if not cadastro_id_limpo:
                candidatos["nome_norm"] = candidatos["nome"].apply(normalizar_nome)
                por_nome = candidatos[candidatos["nome_norm"] == normalizar_nome(nome_limpo)]
                if not por_nome.empty:
                    cadastro_id_limpo = limpar_id(por_nome.iloc[0].get("cadastro_id"))

    if cadastro_id_limpo:
        return execute_returning(
            """
            UPDATE cadastro.cadastro
            SET
                nome = :nome,
                cpf = :cpf,
                telefone = :telefone,
                email = :email,
                data_nascimento = CAST(:data_nascimento AS DATE),
                participa_curso = COALESCE(participa_curso, false),
                perfil = 'filhe'
            WHERE id = :cadastro_id
            RETURNING id, nome, cpf, telefone, email, data_nascimento, perfil;
            """,
            {
                "cadastro_id": cadastro_id_limpo,
                "nome": nome_limpo,
                "cpf": cpf_limpo,
                "telefone": telefone_limpo,
                "email": email_limpo,
                "data_nascimento": data_nascimento_limpa,
            },
        )

    return execute_returning(
        """
        INSERT INTO cadastro.cadastro
            (nome, cpf, telefone, email, data_nascimento, participa_curso, perfil)
        VALUES
            (:nome, :cpf, :telefone, :email, CAST(:data_nascimento AS DATE), false, 'filhe')
        RETURNING id, nome, cpf, telefone, email, data_nascimento, perfil;
        """,
        {
            "nome": nome_limpo,
            "cpf": cpf_limpo,
            "telefone": telefone_limpo,
            "email": email_limpo,
            "data_nascimento": data_nascimento_limpa,
        },
    )


def sincronizar_planilha_com_cadastro() -> dict:
    ensure_cadastro_conciliacao_ready()
    planilha = carregar_planilha_pessoas()
    if planilha is None or planilha.empty:
        return {"criados": 0, "atualizados": 0, "total_planilha": 0}

    nome_col = _detectar_coluna_nome(planilha)
    cpf_col = _detectar_coluna_opcional(planilha, ("cpf", "documento"))
    telefone_col = _detectar_coluna_opcional(planilha, ("telefone", "whatsapp", "telefone_whatsapp"))
    email_col = _detectar_coluna_opcional(planilha, ("email", "e_mail"))
    nascimento_col = _detectar_coluna_opcional(planilha, ("data_nascimento", "data_de_nascimento", "nascimento"))

    existentes_df = listar_cadastro_todos()
    existentes = {}
    if existentes_df is not None and not existentes_df.empty:
        existentes_df["nome_norm"] = existentes_df["nome"].apply(normalizar_nome)
        existentes = {
            row["nome_norm"]: limpar_id(row["cadastro_id"])
            for _, row in existentes_df.iterrows()
            if row.get("nome_norm")
        }

    criados = 0
    atualizados = 0
    processados = set()
    total_planilha = 0
    for _, row in planilha.iterrows():
        nome = _clean_text(row.get(nome_col))
        if not nome:
            continue
        total_planilha += 1
        nome_norm = normalizar_nome(nome)
        if nome_norm in processados:
            continue
        processados.add(nome_norm)
        if nome_norm in existentes:
            marcar_cadastro_como_filhe(existentes[nome_norm], nome=nome)
            atualizados += 1
            continue
        salvar_pessoa_filhe(
            nome=nome,
            cpf=row.get(cpf_col) if cpf_col else None,
            telefone=row.get(telefone_col) if telefone_col else None,
            email=row.get(email_col) if email_col else None,
            data_nascimento=row.get(nascimento_col) if nascimento_col else None,
        )
        criados += 1

    return {"criados": criados, "atualizados": atualizados, "total_planilha": total_planilha}


def _preparar_comprovantes() -> pd.DataFrame:
    df = run_query(
        """
        SELECT
            comp.id,
            comp.cadastro_id,
            COALESCE(c.nome, comp.nome_informado) AS nome,
            COALESCE(c.cpf, comp.cpf_informado) AS cpf,
            COALESCE(c.telefone, comp.telefone_informado) AS telefone,
            c.email,
            comp.tipo_comprovante,
            comp.mes_referencia,
            comp.valor_informado,
            comp.status,
            comp.observacao_admin,
            comp.arquivo_path,
            comp.created_at
        FROM atendimento.comprovantes comp
        LEFT JOIN cadastro.cadastro c
            ON c.id = comp.cadastro_id
        WHERE comp.tipo_comprovante IN ('mensalidade', 'contribuicao_voluntaria', 'pac_contribuicao')
        ORDER BY comp.created_at DESC;
        """
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df["nome_norm"] = df["nome"].apply(normalizar_nome)
    df["status_label"] = df["status"].apply(lambda value: label_status(value, True))
    df["tipo_label"] = df["tipo_comprovante"].apply(label_tipo)
    return df


def listar_movimentacoes_financeiras() -> pd.DataFrame:
    return _preparar_comprovantes()


def montar_conciliacao(mes_referencia: str | None = None) -> pd.DataFrame:
    mes_referencia = mes_referencia or mes_atual()
    pessoas = _preparar_pessoas(carregar_pessoas_base())
    comprovantes = _preparar_comprovantes()

    if comprovantes.empty:
        pessoas["comprovante_id"] = None
        pessoas["tem_comprovante"] = False
        pessoas["tipo_comprovante"] = "mensalidade"
        pessoas["tipo_label"] = "Mensalidade"
        pessoas["mes_referencia"] = mes_referencia
        pessoas["valor_informado"] = 0
        pessoas["status"] = "pendente"
        pessoas["status_label"] = "Pendente"
        pessoas["created_at"] = None
        pessoas["observacao_admin"] = None
        pessoas["arquivo_path"] = None
        return pessoas

    mov_mes = comprovantes[comprovantes["mes_referencia"].astype(str) == str(mes_referencia)].copy()
    mov_mes = mov_mes.sort_values("created_at", ascending=False).drop_duplicates(subset=["nome_norm"])
    merged = pessoas.merge(
        mov_mes,
        on="nome_norm",
        how="left",
        suffixes=("", "_mov"),
    )
    merged["comprovante_id"] = merged["id"].apply(limpar_id)
    merged["tem_comprovante"] = merged["comprovante_id"].notna()
    merged["tipo_comprovante"] = merged["tipo_comprovante"].fillna("mensalidade")
    merged["tipo_label"] = merged["tipo_comprovante"].apply(label_tipo)
    merged["mes_referencia"] = merged["mes_referencia"].fillna(mes_referencia)
    merged["valor_informado"] = pd.to_numeric(merged["valor_informado"], errors="coerce").fillna(0)
    merged["status"] = merged["status"].fillna("pendente")
    merged["status_label"] = merged.apply(
        lambda row: label_status(row.get("status"), row.get("tem_comprovante")),
        axis=1,
    )
    for col in ["cpf", "telefone", "email"]:
        mov_col = f"{col}_mov"
        if mov_col in merged:
            merged[col] = merged[col].fillna(merged[mov_col])
    return merged.sort_values(["status_label", "nome"])


def meses_disponiveis() -> list[str]:
    comprovantes = _preparar_comprovantes()
    meses = set()
    if not comprovantes.empty and "mes_referencia" in comprovantes:
        meses.update(
            comprovantes["mes_referencia"].dropna().astype(str).loc[
                comprovantes["mes_referencia"].dropna().astype(str).str.match(r"^\d{2}/\d{4}$")
            ].tolist()
        )
    meses.add(mes_atual())
    return sorted(meses, key=lambda item: (item[-4:], item[:2]), reverse=True)


def resumo_financeiro(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"total": 0, "valor_total": 0, "valor_pago": 0, "valor_pendente": 0, "pendentes": 0, "aprovados": 0}
    valores = pd.to_numeric(df.get("valor_informado"), errors="coerce").fillna(0)
    status = df.get("status_label", pd.Series([""] * len(df))).astype(str).str.lower()
    pago = status.eq("aprovado")
    pendente = ~pago
    return {
        "total": int(len(df)),
        "valor_total": float(valores.sum()),
        "valor_pago": float(valores[pago].sum()),
        "valor_pendente": float(valores[pendente].sum()),
        "pendentes": int(status.eq("pendente").sum()),
        "aprovados": int(pago.sum()),
    }
