# services/pac_service.py

from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata

import pandas as pd

from db.database import execute_returning, run_query
from services.cadastro_service import only_digits, salvar_ou_vincular_cadastro_pac


# =========================================================
# PAC - Solicitações antigas/compatibilidade
# =========================================================

def registrar_solicitacao_pac(
    cadastro_id: int | None,
    tipo_solicitacao: str,
    nome_informado: str | None = None,
    cpf_informado: str | None = None,
    telefone_informado: str | None = None,
    descricao: str | None = None,
) -> dict:
    garantir_estrutura_pac()
    return execute_returning(
        """
        INSERT INTO atendimento.pac_solicitacoes
        (
            cadastro_id,
            nome_informado,
            cpf_informado,
            telefone_informado,
            tipo_solicitacao,
            descricao,
            status
        )
        VALUES
        (
            :cadastro_id,
            :nome_informado,
            :cpf_informado,
            :telefone_informado,
            :tipo_solicitacao,
            :descricao,
            'novo'
        )
        RETURNING
            id,
            cadastro_id,
            nome_informado,
            cpf_informado,
            telefone_informado,
            tipo_solicitacao,
            descricao,
            status,
            created_at;
        """,
        {
            "cadastro_id": cadastro_id,
            "nome_informado": nome_informado,
            "cpf_informado": only_digits(cpf_informado),
            "telefone_informado": only_digits(telefone_informado),
            "tipo_solicitacao": tipo_solicitacao,
            "descricao": descricao,
        },
    )


def cadastrar_assistido_pac(
    nome: str,
    cpf: str,
    email: str,
    data_nascimento,
    telefone: str,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
    descricao: str | None = None,
) -> dict:
    resultado_cadastro = salvar_ou_vincular_cadastro_pac(
        nome=nome,
        cpf=cpf,
        email=email,
        data_nascimento=data_nascimento,
        telefone=telefone,
        responsavel_nome=responsavel_nome,
        responsavel_cpf=responsavel_cpf,
    )
    cadastro = resultado_cadastro["cadastro"]
    solicitacao = registrar_solicitacao_pac(
        cadastro_id=cadastro.get("id"),
        tipo_solicitacao="cadastro_assistido",
        nome_informado=nome,
        cpf_informado=cpf,
        telefone_informado=telefone,
        descricao=descricao,
    )
    return {"acao_cadastro": resultado_cadastro["acao"], "cadastro": cadastro, "solicitacao": solicitacao}


def listar_solicitacoes_pac(status: str | None = None):
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            p.id,
            p.cadastro_id,
            COALESCE(c.nome, p.nome_informado) AS nome,
            COALESCE(c.cpf, p.cpf_informado) AS cpf,
            COALESCE(c.telefone, p.telefone_informado) AS telefone,
            c.email,
            c.perfil,
            p.tipo_solicitacao,
            p.descricao,
            p.status,
            p.created_at
        FROM atendimento.pac_solicitacoes p
        LEFT JOIN cadastro.cadastro c
            ON c.id = p.cadastro_id
        WHERE (:status IS NULL OR p.status = :status)
        ORDER BY p.created_at DESC;
        """,
        {"status": status},
    )


def atualizar_status_solicitacao_pac(solicitacao_id: int, status: str) -> dict:
    garantir_estrutura_pac()
    return execute_returning(
        """
        UPDATE atendimento.pac_solicitacoes
        SET status = :status, updated_at = NOW()
        WHERE id = :solicitacao_id
        RETURNING id, status, updated_at;
        """,
        {"solicitacao_id": solicitacao_id, "status": status},
    )


# =========================================================
# PAC - Cadastro assistido, crianças e apadrinhamento
# =========================================================

def calcular_idade(data_nascimento) -> int | None:
    if data_nascimento is None:
        return None
    if isinstance(data_nascimento, datetime):
        data_nascimento = data_nascimento.date()
    if isinstance(data_nascimento, str):
        data_nascimento = datetime.strptime(data_nascimento[:10], "%Y-%m-%d").date()
    hoje = date.today()
    return hoje.year - data_nascimento.year - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))


def _normalizar_data(data_value):
    if isinstance(data_value, datetime):
        return data_value.date()
    if isinstance(data_value, date):
        return data_value
    if isinstance(data_value, str):
        return datetime.strptime(data_value[:10], "%Y-%m-%d").date()
    raise ValueError("Data de nascimento inválida.")


def _normalizar_texto(value: str | None) -> str:
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def garantir_estrutura_pac() -> None:
    """Cria/ajusta estruturas sem quebrar outros projetos que usam cadastro.cadastro."""
    from db.database import execute_command

    execute_command("CREATE SCHEMA IF NOT EXISTS atendimento;")
    execute_command("CREATE SCHEMA IF NOT EXISTS cadastro;")

    execute_command(
        """
        ALTER TABLE cadastro.cadastro
            ADD COLUMN IF NOT EXISTS idade INTEGER,
            ADD COLUMN IF NOT EXISTS sexo VARCHAR(30),
            ADD COLUMN IF NOT EXISTS possui_deficiencia BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS descricao_deficiencia TEXT,
            ADD COLUMN IF NOT EXISTS etnia VARCHAR(30),
            ADD COLUMN IF NOT EXISTS dados_compartilhamento BOOLEAN DEFAULT FALSE;
        """
    )

    execute_command(
        """
        CREATE TABLE IF NOT EXISTS atendimento.pac_solicitacoes (
            id SERIAL PRIMARY KEY,
            cadastro_id INTEGER,
            nome_informado VARCHAR(200),
            cpf_informado VARCHAR(20),
            telefone_informado VARCHAR(30),
            tipo_solicitacao VARCHAR(80),
            descricao TEXT,
            status VARCHAR(30) DEFAULT 'novo',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
    )

    execute_command(
        """
        CREATE TABLE IF NOT EXISTS cadastro._pac_criancas (
            id SERIAL PRIMARY KEY,
            crianca_cpf VARCHAR(20) NOT NULL UNIQUE,
            crianca_nome VARCHAR(200) NOT NULL,
            padrinho_cpf VARCHAR(20),
            padrinho_nome VARCHAR(200),
            data_apadrinhamento TIMESTAMP WITH TIME ZONE
        );
        """
    )

    execute_command(
        """
        UPDATE cadastro.cadastro
        SET idade = DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT
        WHERE data_nascimento IS NOT NULL
          AND (idade IS NULL OR idade <> DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT);
        """
    )

    sincronizar_pac_criancas()


def sincronizar_pac_criancas() -> None:
    """Mantém cadastro._pac_criancas refletindo crianças PAC da tabela mestre."""
    from db.database import execute_command

    execute_command(
        """
        INSERT INTO cadastro._pac_criancas (crianca_cpf, crianca_nome)
        SELECT DISTINCT
            c.cpf AS crianca_cpf,
            c.nome AS crianca_nome
        FROM cadastro.cadastro c
        WHERE LOWER(COALESCE(c.perfil, '')) = 'pac'
          AND COALESCE(c.idade, 999) < 18
          AND c.cpf IS NOT NULL
          AND TRIM(c.cpf) <> ''
        ON CONFLICT (crianca_cpf)
        DO UPDATE SET crianca_nome = EXCLUDED.crianca_nome;
        """
    )


def _buscar_cadastro_por_documento(documento: str | None) -> dict | None:
    documento_limpo = only_digits(documento)
    if not documento_limpo:
        return None
    from db.database import fetch_one
    return fetch_one("SELECT * FROM cadastro.cadastro WHERE cpf = :cpf LIMIT 1;", {"cpf": documento_limpo})


def salvar_cadastro_pac_completo(
    nome: str,
    documento: str,
    email: str | None,
    telefone: str | None,
    data_nascimento,
    sexo: str,
    possui_deficiencia: bool,
    descricao_deficiencia: str | None,
    etnia: str,
    dados_compartilhamento: bool,
    responsavel_nome: str | None = None,
    responsavel_cpf: str | None = None,
) -> dict:
    garantir_estrutura_pac()

    if not nome or not nome.strip():
        raise ValueError("Nome completo é obrigatório.")
    if not documento or not only_digits(documento):
        raise ValueError("Documento é obrigatório.")
    if not data_nascimento:
        raise ValueError("Data de nascimento é obrigatória.")
    if not sexo:
        raise ValueError("Sexo é obrigatório.")
    if not etnia:
        raise ValueError("Etnia é obrigatória.")
    if not dados_compartilhamento:
        raise ValueError("É necessário concordar com o compartilhamento dos dados.")

    data_nascimento_date = _normalizar_data(data_nascimento)
    idade = calcular_idade(data_nascimento_date)
    menor_idade = bool(idade is not None and idade < 18)

    if menor_idade:
        if not responsavel_nome or not responsavel_nome.strip():
            raise ValueError("Nome do responsável é obrigatório para menor de idade.")
        if not responsavel_cpf or not only_digits(responsavel_cpf):
            raise ValueError("CPF do responsável é obrigatório para menor de idade.")

    documento_limpo = only_digits(documento)
    telefone_limpo = only_digits(telefone)
    responsavel_cpf_limpo = only_digits(responsavel_cpf)
    existente = _buscar_cadastro_por_documento(documento_limpo)

    params = {
        "nome": nome.strip(),
        "cpf": documento_limpo,
        "email": email.strip().lower() if email else None,
        "telefone": telefone_limpo,
        "data_nascimento": data_nascimento_date,
        "idade": idade,
        "menor_idade": menor_idade,
        "responsavel_nome": responsavel_nome.strip() if responsavel_nome else None,
        "responsavel_cpf": responsavel_cpf_limpo,
        "sexo": sexo,
        "possui_deficiencia": bool(possui_deficiencia),
        "descricao_deficiencia": descricao_deficiencia.strip() if descricao_deficiencia else None,
        "etnia": etnia,
        "dados_compartilhamento": bool(dados_compartilhamento),
    }

    if existente:
        cadastro = execute_returning(
            """
            UPDATE cadastro.cadastro
            SET
                nome = :nome,
                email = COALESCE(:email, email),
                telefone = COALESCE(:telefone, telefone),
                data_nascimento = :data_nascimento,
                idade = :idade,
                menor_idade = :menor_idade,
                responsavel_nome = :responsavel_nome,
                responsavel_cpf = :responsavel_cpf,
                sexo = :sexo,
                possui_deficiencia = :possui_deficiencia,
                descricao_deficiencia = :descricao_deficiencia,
                etnia = :etnia,
                dados_compartilhamento = :dados_compartilhamento,
                participa_curso = COALESCE(participa_curso, false),
                perfil = CASE
                    WHEN perfil IS NULL OR TRIM(perfil) = '' THEN 'pac'
                    WHEN LOWER(perfil) = 'pac' THEN 'pac'
                    ELSE perfil
                END
            WHERE cpf = :cpf
            RETURNING *;
            """,
            params,
        )
        sincronizar_pac_criancas()
        return {"acao": "atualizado", "cadastro": cadastro}

    cadastro = execute_returning(
        """
        INSERT INTO cadastro.cadastro
        (
            nome, cpf, email, participa_curso, perfil, data_nascimento,
            idade, menor_idade, responsavel_nome, responsavel_cpf, telefone,
            sexo, possui_deficiencia, descricao_deficiencia, etnia, dados_compartilhamento
        )
        VALUES
        (
            :nome, :cpf, :email, false, 'pac', :data_nascimento,
            :idade, :menor_idade, :responsavel_nome, :responsavel_cpf, :telefone,
            :sexo, :possui_deficiencia, :descricao_deficiencia, :etnia, :dados_compartilhamento
        )
        RETURNING *;
        """,
        params,
    )
    sincronizar_pac_criancas()
    return {"acao": "criado", "cadastro": cadastro}


def cadastrar_familia_pac(responsavel: dict, filhos: list[dict] | None = None) -> dict:
    filhos = filhos or []
    garantir_estrutura_pac()

    resp = salvar_cadastro_pac_completo(
        nome=responsavel["nome"],
        documento=responsavel["cpf"],
        email=responsavel["email"],
        telefone=responsavel["telefone"],
        data_nascimento=responsavel["data_nascimento"],
        sexo=responsavel["sexo"],
        possui_deficiencia=responsavel.get("possui_deficiencia", False),
        descricao_deficiencia=responsavel.get("descricao_deficiencia"),
        etnia=responsavel["etnia"],
        dados_compartilhamento=responsavel.get("dados_compartilhamento", False),
    )

    cad_resp = resp["cadastro"]
    criancas = []
    for filho in filhos:
        child = salvar_cadastro_pac_completo(
            nome=filho["nome"],
            documento=filho["documento"],
            email=responsavel["email"],
            telefone=responsavel["telefone"],
            data_nascimento=filho["data_nascimento"],
            sexo=filho["sexo"],
            possui_deficiencia=filho.get("possui_deficiencia", False),
            descricao_deficiencia=filho.get("descricao_deficiencia"),
            etnia=filho["etnia"],
            dados_compartilhamento=responsavel.get("dados_compartilhamento", False),
            responsavel_nome=cad_resp.get("nome"),
            responsavel_cpf=cad_resp.get("cpf"),
        )
        criancas.append(child)

    solicitacao = registrar_solicitacao_pac(
        cadastro_id=cad_resp.get("id"),
        tipo_solicitacao="cadastro_assistido",
        nome_informado=cad_resp.get("nome"),
        cpf_informado=cad_resp.get("cpf"),
        telefone_informado=cad_resp.get("telefone"),
        descricao=f"Cadastro assistido PAC. Filhos informados: {len(criancas)}.",
    )
    sincronizar_pac_criancas()
    return {"responsavel": resp, "filhos": criancas, "solicitacao": solicitacao}


def listar_pac_cadastros():
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            id, nome, cpf, email, telefone, data_nascimento, idade, menor_idade,
            responsavel_nome, responsavel_cpf, sexo, possui_deficiencia,
            descricao_deficiencia, etnia, dados_compartilhamento, perfil
        FROM cadastro.cadastro
        WHERE LOWER(COALESCE(perfil, '')) = 'pac'
        ORDER BY nome;
        """
    )


def listar_criancas_pac():
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            pc.id,
            c.id AS cadastro_id,
            pc.crianca_nome,
            pc.crianca_cpf,
            c.idade,
            c.sexo,
            c.etnia,
            c.possui_deficiencia,
            c.descricao_deficiencia,
            c.responsavel_nome,
            c.responsavel_cpf,
            r.telefone AS responsavel_telefone,
            r.email AS responsavel_email,
            CASE WHEN pc.padrinho_cpf IS NULL THEN 'não apadrinhada' ELSE 'apadrinhada' END AS apadrinhamento,
            pc.padrinho_nome,
            pc.padrinho_cpf,
            pc.data_apadrinhamento
        FROM cadastro._pac_criancas pc
        INNER JOIN cadastro.cadastro c
            ON c.cpf = pc.crianca_cpf
           AND LOWER(COALESCE(c.perfil, '')) = 'pac'
           AND COALESCE(c.idade, 999) < 18
        LEFT JOIN cadastro.cadastro r
            ON r.cpf = c.responsavel_cpf
        ORDER BY pc.crianca_nome;
        """
    )


def listar_responsaveis_pac():
    """
    Lista mães/responsáveis PAC.

    Regra solicitada no admin:
    - perfil = 'pac'
    - menor_idade = false

    A quantidade de filhos é calculada por vínculo em responsavel_cpf.
    Mantive fallback por idade para bases antigas em que menor_idade possa estar nulo.
    """
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            r.nome,
            r.cpf,
            r.telefone,
            r.email,
            r.idade,
            COALESCE(COUNT(DISTINCT c.cpf), 0) AS quantidade_filhos
        FROM cadastro.cadastro r
        LEFT JOIN cadastro.cadastro c
            ON c.responsavel_cpf = r.cpf
           AND LOWER(COALESCE(c.perfil, '')) = 'pac'
           AND (
                c.menor_idade IS TRUE
                OR COALESCE(c.idade, 999) < 18
           )
        WHERE LOWER(COALESCE(r.perfil, '')) = 'pac'
          AND (
                r.menor_idade IS FALSE
                OR COALESCE(r.idade, 0) >= 18
          )
        GROUP BY r.nome, r.cpf, r.telefone, r.email, r.idade
        ORDER BY r.nome;
        """
    )


def listar_filhos_por_responsavel(responsavel_cpf: str):
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            pc.crianca_nome AS nome,
            pc.crianca_cpf AS cpf,
            c.idade,
            c.sexo,
            c.etnia,
            c.possui_deficiencia,
            c.descricao_deficiencia,
            CASE WHEN pc.padrinho_cpf IS NULL THEN 'não apadrinhada' ELSE 'apadrinhada' END AS apadrinhamento,
            pc.padrinho_nome,
            pc.data_apadrinhamento
        FROM cadastro._pac_criancas pc
        INNER JOIN cadastro.cadastro c
            ON c.cpf = pc.crianca_cpf
        WHERE c.responsavel_cpf = :responsavel_cpf
          AND LOWER(COALESCE(c.perfil, '')) = 'pac'
          AND COALESCE(c.idade, 999) < 18
        ORDER BY c.idade, pc.crianca_nome;
        """,
        {"responsavel_cpf": only_digits(responsavel_cpf)},
    )


def listar_filhes_santo_apadrinhamento():
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT id, nome, cpf
        FROM cadastro.cadastro
        WHERE LOWER(COALESCE(perfil, '')) = 'filhes'
        ORDER BY nome;
        """
    )


def listar_criancas_disponiveis_apadrinhamento():
    garantir_estrutura_pac()
    return run_query(
        """
        SELECT
            c.id AS cadastro_id,
            pc.crianca_nome AS nome,
            pc.crianca_cpf AS cpf,
            c.idade,
            c.sexo
        FROM cadastro._pac_criancas pc
        INNER JOIN cadastro.cadastro c
            ON c.cpf = pc.crianca_cpf
        WHERE pc.padrinho_cpf IS NULL
          AND LOWER(COALESCE(c.perfil, '')) = 'pac'
          AND COALESCE(c.idade, 999) < 18
          AND LOWER(COALESCE(c.sexo, '')) IN ('masculino', 'masc', 'm')
        ORDER BY c.idade, pc.crianca_nome;
        """
    )


def registrar_apadrinhamento_pac(padrinho_cadastro_id: int, crianca_cadastro_id: int) -> dict:
    garantir_estrutura_pac()
    return execute_returning(
        """
        WITH padrinho AS (
            SELECT id, nome, cpf
            FROM cadastro.cadastro
            WHERE id = :padrinho_id
              AND LOWER(COALESCE(perfil, '')) = 'filhes'
        ), crianca AS (
            SELECT id, nome, cpf
            FROM cadastro.cadastro
            WHERE id = :crianca_id
              AND LOWER(COALESCE(perfil, '')) = 'pac'
              AND COALESCE(idade, 999) < 18
        )
        UPDATE cadastro._pac_criancas pc
        SET
            padrinho_cpf = p.cpf,
            padrinho_nome = p.nome,
            data_apadrinhamento = NOW()
        FROM padrinho p
        CROSS JOIN crianca c
        WHERE pc.crianca_cpf = c.cpf
        RETURNING
            pc.id,
            pc.crianca_cpf,
            pc.crianca_nome,
            pc.padrinho_cpf,
            pc.padrinho_nome,
            pc.data_apadrinhamento;
        """,
        {"padrinho_id": padrinho_cadastro_id, "crianca_id": crianca_cadastro_id},
    )
