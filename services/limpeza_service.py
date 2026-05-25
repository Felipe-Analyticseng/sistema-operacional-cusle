# services/limpeza_service.py

from datetime import date, datetime

from db.database import execute_returning, run_query
from services.cadastro_service import buscar_cadastro_por_cpf, only_digits


def normalizar_data_faxina(data_value) -> date:
    """
    Aceita date, datetime ou string no formato YYYY-MM-DD.
    """
    if isinstance(data_value, datetime):
        return data_value.date()

    if isinstance(data_value, date):
        return data_value

    if isinstance(data_value, str):
        return datetime.strptime(data_value, "%Y-%m-%d").date()

    raise ValueError("Data da faxina inválida.")


def registrar_limpeza(
    nome: str,
    cpf: str | None,
    data_faxina,
    observacao: str | None = None,
) -> dict:
    """
    Registra participação na lista de limpeza/faxina.

    Se o CPF existir em cadastro.cadastro, vincula cadastro_id.
    Se não existir, salva apenas os dados informados.
    """
    if not nome or not nome.strip():
        raise ValueError("Nome é obrigatório.")

    data_faxina_date = normalizar_data_faxina(data_faxina)

    cpf_limpo = only_digits(cpf)
    cadastro_id = None

    if cpf_limpo:
        cadastro = buscar_cadastro_por_cpf(cpf_limpo)
        if cadastro:
            cadastro_id = cadastro.get("id")

    return execute_returning(
        """
        INSERT INTO atendimento.limpeza_registros
        (
            cadastro_id,
            nome_informado,
            cpf_informado,
            data_faxina,
            observacao
        )
        VALUES
        (
            :cadastro_id,
            :nome_informado,
            :cpf_informado,
            :data_faxina,
            :observacao
        )
        RETURNING
            id,
            cadastro_id,
            nome_informado,
            cpf_informado,
            data_faxina,
            observacao,
            created_at;
        """,
        {
            "cadastro_id": cadastro_id,
            "nome_informado": nome.strip(),
            "cpf_informado": cpf_limpo,
            "data_faxina": data_faxina_date,
            "observacao": observacao.strip() if observacao else None,
        },
    )


def listar_limpeza():
    """
    Lista registros de limpeza/faxina.
    """
    return run_query(
        """
        SELECT
            l.id,
            l.cadastro_id,
            COALESCE(c.nome, l.nome_informado) AS nome,
            COALESCE(c.cpf, l.cpf_informado) AS cpf,
            l.data_faxina,
            l.observacao,
            l.created_at
        FROM atendimento.limpeza_registros l
        LEFT JOIN cadastro.cadastro c
            ON c.id = l.cadastro_id
        ORDER BY l.data_faxina DESC, l.created_at DESC;
        """
    )