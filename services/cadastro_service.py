# services/cadastro_service.py

import math
import re
from datetime import date, datetime

from db.database import fetch_one, execute_returning


def only_digits(value: str | int | float | None) -> str | None:
    """
    Remove tudo que não for número.
    Exemplo:
    999.999.999-99 -> 99999999999
    (11) 99999-9999 -> 11999999999
    """
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    value_str = str(value).strip()
    if not value_str or value_str.lower() == "nan":
        return None

    digits = re.sub(r"\D", "", value_str)
    return digits or None


def calcular_menor_idade(data_nascimento: date) -> bool:
    """
    Retorna True se a pessoa tiver menos de 18 anos.
    """
    hoje = date.today()

    idade = hoje.year - data_nascimento.year - (
        (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day)
    )

    return idade < 18


def normalizar_data(data_value) -> date:
    """
    Aceita date, datetime ou string no formato YYYY-MM-DD.
    """
    if isinstance(data_value, datetime):
        return data_value.date()

    if isinstance(data_value, date):
        return data_value

    if isinstance(data_value, str):
        return datetime.strptime(data_value, "%Y-%m-%d").date()

    raise ValueError("Data de nascimento inválida.")


def validar_dados_menor_idade(
    data_nascimento,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
) -> bool:
    """
    Valida se, em caso de menor de idade, os dados do responsável foram informados.
    Retorna True se for menor de idade.
    """
    data_nascimento_date = normalizar_data(data_nascimento)
    menor_idade = calcular_menor_idade(data_nascimento_date)

    if menor_idade:
        if not responsavel_nome or not responsavel_nome.strip():
            raise ValueError("Nome do responsável é obrigatório para menor de idade.")

        if not responsavel_cpf or not only_digits(responsavel_cpf):
            raise ValueError("CPF do responsável é obrigatório para menor de idade.")

    return menor_idade


def buscar_cadastro_por_cpf(cpf: str) -> dict | None:
    """
    Busca uma pessoa na tabela cadastro.cadastro pelo CPF normalizado.
    """
    cpf_limpo = only_digits(cpf)

    if not cpf_limpo:
        return None

    return fetch_one(
        """
        SELECT
            id,
            nome,
            email,
            cpf,
            participa_curso,
            perfil,
            telefone,
            data_nascimento,
            menor_idade,
            responsavel_nome,
            responsavel_cpf
        FROM cadastro.cadastro
        WHERE cpf = :cpf
        LIMIT 1;
        """,
        {
            "cpf": cpf_limpo,
        },
    )


def criar_cadastro_pac(
    nome: str,
    cpf: str,
    email: str,
    data_nascimento,
    telefone: str,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
) -> dict:
    """
    Cria um novo cadastro em cadastro.cadastro com perfil = 'pac'.

    Regra:
    - perfil = 'pac'
    - participa_curso = false
    - se menor de idade, responsável é obrigatório
    """
    cpf_limpo = only_digits(cpf)
    telefone_limpo = only_digits(telefone)
    data_nascimento_date = normalizar_data(data_nascimento)

    menor_idade = validar_dados_menor_idade(
        data_nascimento=data_nascimento_date,
        responsavel_nome=responsavel_nome,
        responsavel_cpf=responsavel_cpf,
    )

    responsavel_cpf_limpo = only_digits(responsavel_cpf)

    return execute_returning(
        """
        INSERT INTO cadastro.cadastro
        (
            nome,
            cpf,
            email,
            participa_curso,
            perfil,
            data_nascimento,
            menor_idade,
            responsavel_nome,
            responsavel_cpf,
            telefone
        )
        VALUES
        (
            :nome,
            :cpf,
            :email,
            :participa_curso,
            'pac',
            :data_nascimento,
            :menor_idade,
            :responsavel_nome,
            :responsavel_cpf,
            :telefone
        )
        RETURNING
            id,
            nome,
            cpf,
            email,
            participa_curso,
            perfil,
            telefone,
            data_nascimento,
            menor_idade,
            responsavel_nome,
            responsavel_cpf;
        """,
        {
            "nome": nome.strip(),
            "cpf": cpf_limpo,
            "email": email.strip().lower(),
            "participa_curso": False,
            "data_nascimento": data_nascimento_date,
            "menor_idade": menor_idade,
            "responsavel_nome": responsavel_nome.strip() if responsavel_nome else None,
            "responsavel_cpf": responsavel_cpf_limpo,
            "telefone": telefone_limpo,
        },
    )


def atualizar_cadastro_existente_para_pac(
    cadastro_id: int,
    nome: str,
    cpf: str,
    email: str,
    data_nascimento,
    telefone: str,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
) -> dict:
    """
    Atualiza cadastro existente quando o perfil está vazio/nulo.

    Regra:
    - Só será chamada quando o perfil atual estiver vazio ou nulo.
    - Atualiza perfil para 'pac'.
    - Garante participa_curso = false caso esteja nulo.
    """
    cpf_limpo = only_digits(cpf)
    telefone_limpo = only_digits(telefone)
    data_nascimento_date = normalizar_data(data_nascimento)

    menor_idade = validar_dados_menor_idade(
        data_nascimento=data_nascimento_date,
        responsavel_nome=responsavel_nome,
        responsavel_cpf=responsavel_cpf,
    )

    responsavel_cpf_limpo = only_digits(responsavel_cpf)

    return execute_returning(
        """
        UPDATE cadastro.cadastro
        SET
            nome = :nome,
            cpf = :cpf,
            email = :email,
            participa_curso = COALESCE(participa_curso, false),
            data_nascimento = :data_nascimento,
            menor_idade = :menor_idade,
            responsavel_nome = :responsavel_nome,
            responsavel_cpf = :responsavel_cpf,
            telefone = :telefone,
            perfil = 'pac'
        WHERE id = :cadastro_id
        RETURNING
            id,
            nome,
            cpf,
            email,
            participa_curso,
            perfil,
            telefone,
            data_nascimento,
            menor_idade,
            responsavel_nome,
            responsavel_cpf;
        """,
        {
            "cadastro_id": cadastro_id,
            "nome": nome.strip(),
            "cpf": cpf_limpo,
            "email": email.strip().lower(),
            "data_nascimento": data_nascimento_date,
            "menor_idade": menor_idade,
            "responsavel_nome": responsavel_nome.strip() if responsavel_nome else None,
            "responsavel_cpf": responsavel_cpf_limpo,
            "telefone": telefone_limpo,
        },
    )


def salvar_ou_vincular_cadastro_pac(
    nome: str,
    cpf: str,
    email: str,
    data_nascimento,
    telefone: str,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
) -> dict:
    """
    Regra principal do cadastro PAC.

    CPF novo:
        cria cadastro em cadastro.cadastro com perfil = 'pac'.

    CPF existente com perfil vazio/null:
        atualiza cadastro e define perfil = 'pac'.

    CPF existente com perfil diferente:
        preserva perfil original e apenas retorna o cadastro existente.

    Essa função NÃO registra a solicitação PAC.
    A solicitação é registrada no pac_service.py.
    """
    cpf_limpo = only_digits(cpf)

    if not cpf_limpo:
        raise ValueError("CPF é obrigatório.")

    if not nome or not nome.strip():
        raise ValueError("Nome é obrigatório.")

    if not email or not email.strip():
        raise ValueError("E-mail é obrigatório.")

    if not telefone or not only_digits(telefone):
        raise ValueError("Telefone é obrigatório.")

    data_nascimento_date = normalizar_data(data_nascimento)

    validar_dados_menor_idade(
        data_nascimento=data_nascimento_date,
        responsavel_nome=responsavel_nome,
        responsavel_cpf=responsavel_cpf,
    )

    cadastro_existente = buscar_cadastro_por_cpf(cpf_limpo)

    if not cadastro_existente:
        cadastro = criar_cadastro_pac(
            nome=nome,
            cpf=cpf_limpo,
            email=email,
            data_nascimento=data_nascimento_date,
            telefone=telefone,
            responsavel_nome=responsavel_nome,
            responsavel_cpf=responsavel_cpf,
        )

        return {
            "acao": "criado",
            "cadastro": cadastro,
        }

    perfil_atual = cadastro_existente.get("perfil")

    if perfil_atual is None or str(perfil_atual).strip() == "":
        cadastro = atualizar_cadastro_existente_para_pac(
            cadastro_id=cadastro_existente["id"],
            nome=nome,
            cpf=cpf_limpo,
            email=email,
            data_nascimento=data_nascimento_date,
            telefone=telefone,
            responsavel_nome=responsavel_nome,
            responsavel_cpf=responsavel_cpf,
        )

        return {
            "acao": "atualizado_para_pac",
            "cadastro": cadastro,
        }

    return {
        "acao": "existente_perfil_preservado",
        "cadastro": cadastro_existente,
    }
