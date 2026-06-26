# services/pac_service.py

from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata

import pandas as pd

from db.database import execute_command, execute_returning, run_query
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
        LEFT JOIN cadastro.cadastro_pac c
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
    """Cria/ajusta estruturas PAC sem quebrar cadastro.cadastro."""
    execute_command("CREATE SCHEMA IF NOT EXISTS atendimento;")
    execute_command("CREATE SCHEMA IF NOT EXISTS cadastro;")

    execute_command(
        """
        CREATE TABLE IF NOT EXISTS cadastro.cadastro_pac (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            cpf VARCHAR(20) NOT NULL,
            telefone VARCHAR(30),
            perfil VARCHAR(50) DEFAULT 'pac',
            participa_curso BOOLEAN DEFAULT FALSE,
            data_nascimento DATE,
            idade INTEGER,
            menor_idade BOOLEAN,
            responsavel_nome VARCHAR(200),
            responsavel_cpf VARCHAR(20),
            sexo VARCHAR(30),
            possui_deficiencia BOOLEAN DEFAULT FALSE,
            descricao_deficiencia TEXT,
            etnia VARCHAR(30),
            dados_compartilhamento BOOLEAN DEFAULT FALSE,
            foto_path TEXT,
            nome_social VARCHAR(200),
            endereco_completo TEXT,
            estado_civil VARCHAR(100),
            com_quem_mora TEXT,
            situacao_trabalho VARCHAR(120),
            renda_mensal VARCHAR(120),
            renda_familiar VARCHAR(120),
            cadastro_unico VARCHAR(120),
            beneficios TEXT,
            problema_saude TEXT,
            medicacao_continua TEXT,
            acompanhamento_psicologico VARCHAR(80),
            alergia TEXT,
            filho_saude_alergia TEXT,
            filho_medicacao TEXT,
            refeicoes_dia VARCHAR(120),
            moradia VARCHAR(80),
            saneamento_basico VARCHAR(80),
            apoio_interesse TEXT,
            dificuldades TEXT,
            pode_oficina TEXT,
            rg_cpf TEXT,
            sugestao_pac TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
    )

    execute_command(
        """
        ALTER TABLE cadastro.cadastro_pac
            ADD COLUMN IF NOT EXISTS participa_curso BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS foto_path TEXT,
            ADD COLUMN IF NOT EXISTS nome_social VARCHAR(200),
            ADD COLUMN IF NOT EXISTS endereco_completo TEXT,
            ADD COLUMN IF NOT EXISTS estado_civil VARCHAR(100),
            ADD COLUMN IF NOT EXISTS com_quem_mora TEXT,
            ADD COLUMN IF NOT EXISTS situacao_trabalho VARCHAR(120),
            ADD COLUMN IF NOT EXISTS renda_mensal VARCHAR(120),
            ADD COLUMN IF NOT EXISTS renda_familiar VARCHAR(120),
            ADD COLUMN IF NOT EXISTS cadastro_unico VARCHAR(120),
            ADD COLUMN IF NOT EXISTS beneficios TEXT,
            ADD COLUMN IF NOT EXISTS problema_saude TEXT,
            ADD COLUMN IF NOT EXISTS medicacao_continua TEXT,
            ADD COLUMN IF NOT EXISTS acompanhamento_psicologico VARCHAR(80),
            ADD COLUMN IF NOT EXISTS alergia TEXT,
            ADD COLUMN IF NOT EXISTS filho_saude_alergia TEXT,
            ADD COLUMN IF NOT EXISTS filho_medicacao TEXT,
            ADD COLUMN IF NOT EXISTS refeicoes_dia VARCHAR(120),
            ADD COLUMN IF NOT EXISTS moradia VARCHAR(80),
            ADD COLUMN IF NOT EXISTS saneamento_basico VARCHAR(80),
            ADD COLUMN IF NOT EXISTS apoio_interesse TEXT,
            ADD COLUMN IF NOT EXISTS dificuldades TEXT,
            ADD COLUMN IF NOT EXISTS pode_oficina TEXT,
            ADD COLUMN IF NOT EXISTS rg_cpf TEXT,
            ADD COLUMN IF NOT EXISTS sugestao_pac TEXT,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
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
        UPDATE cadastro.cadastro_pac
        SET idade = DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT
        WHERE data_nascimento IS NOT NULL
          AND (idade IS NULL OR idade <> DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT);
        """
    )

    migrar_legado_cadastro_para_pac()
    sincronizar_pac_criancas()


PAC_EDIT_FIELDS = [
    "nome",
    "nome_social",
    "cpf",
    "email",
    "telefone",
    "data_nascimento",
    "sexo",
    "etnia",
    "responsavel_nome",
    "responsavel_cpf",
    "endereco_completo",
    "estado_civil",
    "com_quem_mora",
    "situacao_trabalho",
    "renda_mensal",
    "renda_familiar",
    "cadastro_unico",
    "beneficios",
    "problema_saude",
    "medicacao_continua",
    "acompanhamento_psicologico",
    "alergia",
    "possui_deficiencia",
    "descricao_deficiencia",
    "filho_saude_alergia",
    "filho_medicacao",
    "refeicoes_dia",
    "moradia",
    "saneamento_basico",
    "apoio_interesse",
    "dificuldades",
    "pode_oficina",
    "rg_cpf",
    "sugestao_pac",
]


def migrar_legado_cadastro_para_pac() -> None:
    """Replica pessoas PAC legadas de cadastro.cadastro para cadastro.cadastro_pac."""
    execute_command(
        """
        WITH legado AS (
            SELECT DISTINCT ON (regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g'))
                c.*
            FROM cadastro.cadastro c
            WHERE LOWER(COALESCE(c.perfil, '')) = 'pac'
              AND NULLIF(TRIM(COALESCE(c.nome, '')), '') IS NOT NULL
              AND NULLIF(regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g'), '') IS NOT NULL
            ORDER BY regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g'), c.id DESC
        )
        INSERT INTO cadastro.cadastro_pac
        (
            nome, cpf, email, telefone, perfil, participa_curso,
            data_nascimento, idade, menor_idade, responsavel_nome, responsavel_cpf,
            dados_compartilhamento
        )
        SELECT
            TRIM(c.nome) AS nome,
            regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g') AS cpf,
            NULLIF(LOWER(TRIM(COALESCE(c.email, ''))), '') AS email,
            NULLIF(regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '', 'g'), '') AS telefone,
            'pac' AS perfil,
            COALESCE(c.participa_curso, false) AS participa_curso,
            c.data_nascimento,
            CASE
                WHEN c.data_nascimento IS NULL THEN NULL
                ELSE DATE_PART('year', AGE(CURRENT_DATE, c.data_nascimento))::INT
            END AS idade,
            CASE
                WHEN c.menor_idade IS NOT NULL THEN c.menor_idade
                WHEN c.data_nascimento IS NULL THEN NULL
                ELSE DATE_PART('year', AGE(CURRENT_DATE, c.data_nascimento))::INT < 18
            END AS menor_idade,
            NULLIF(TRIM(COALESCE(c.responsavel_nome, '')), '') AS responsavel_nome,
            NULLIF(regexp_replace(COALESCE(c.responsavel_cpf, ''), '[^0-9]', '', 'g'), '') AS responsavel_cpf,
            false AS dados_compartilhamento
        FROM legado c
        WHERE 1 = 1
          AND NOT EXISTS (
              SELECT 1
              FROM cadastro.cadastro_pac cp
              WHERE regexp_replace(COALESCE(cp.cpf, ''), '[^0-9]', '', 'g')
                    = regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g')
          );
        """
    )

    execute_command(
        """
        UPDATE cadastro.cadastro_pac cp
        SET
            nome = COALESCE(NULLIF(TRIM(cp.nome), ''), NULLIF(TRIM(c.nome), '')),
            email = COALESCE(NULLIF(TRIM(cp.email), ''), NULLIF(LOWER(TRIM(COALESCE(c.email, ''))), '')),
            telefone = COALESCE(NULLIF(TRIM(cp.telefone), ''), NULLIF(regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '', 'g'), '')),
            data_nascimento = COALESCE(cp.data_nascimento, c.data_nascimento),
            idade = CASE
                WHEN cp.idade IS NOT NULL THEN cp.idade
                WHEN c.data_nascimento IS NULL THEN NULL
                ELSE DATE_PART('year', AGE(CURRENT_DATE, c.data_nascimento))::INT
            END,
            menor_idade = COALESCE(
                cp.menor_idade,
                c.menor_idade,
                CASE
                    WHEN c.data_nascimento IS NULL THEN NULL
                    ELSE DATE_PART('year', AGE(CURRENT_DATE, c.data_nascimento))::INT < 18
                END
            ),
            responsavel_nome = COALESCE(NULLIF(TRIM(cp.responsavel_nome), ''), NULLIF(TRIM(COALESCE(c.responsavel_nome, '')), '')),
            responsavel_cpf = COALESCE(NULLIF(TRIM(cp.responsavel_cpf), ''), NULLIF(regexp_replace(COALESCE(c.responsavel_cpf, ''), '[^0-9]', '', 'g'), '')),
            participa_curso = COALESCE(cp.participa_curso, c.participa_curso, false),
            perfil = 'pac',
            updated_at = NOW()
        FROM cadastro.cadastro c
        WHERE LOWER(COALESCE(c.perfil, '')) = 'pac'
          AND regexp_replace(COALESCE(cp.cpf, ''), '[^0-9]', '', 'g')
              = regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g');
        """
    )


def atualizar_cadastro_pac_admin(cadastro_id: int, form) -> dict | None:
    garantir_estrutura_pac()

    data_nascimento = (form.get("data_nascimento") or "").strip() or None
    data_nascimento_date = _normalizar_data(data_nascimento) if data_nascimento else None
    idade = calcular_idade(data_nascimento_date) if data_nascimento_date else None
    menor_idade = bool(idade is not None and idade < 18) if idade is not None else None

    params = {
        "id": cadastro_id,
        "nome": (form.get("nome") or "").strip(),
        "nome_social": (form.get("nome_social") or "").strip() or None,
        "cpf": only_digits(form.get("cpf")),
        "email": (form.get("email") or "").strip().lower() or None,
        "telefone": only_digits(form.get("telefone")),
        "data_nascimento": data_nascimento_date,
        "idade": idade,
        "menor_idade": menor_idade,
        "sexo": (form.get("sexo") or "").strip() or None,
        "etnia": (form.get("etnia") or "").strip() or None,
        "responsavel_nome": (form.get("responsavel_nome") or "").strip() or None,
        "responsavel_cpf": only_digits(form.get("responsavel_cpf")),
        "possui_deficiencia": form.get("possui_deficiencia") == "1",
    }
    for field in PAC_EDIT_FIELDS:
        if field not in params and field != "possui_deficiencia":
            params[field] = (form.get(field) or "").strip() or None

    if not params["nome"]:
        raise ValueError("Nome completo e obrigatorio.")
    if not params["cpf"]:
        raise ValueError("CPF e obrigatorio.")

    return execute_returning(
        """
        UPDATE cadastro.cadastro_pac
        SET
            nome = :nome,
            nome_social = :nome_social,
            cpf = :cpf,
            email = :email,
            telefone = :telefone,
            data_nascimento = :data_nascimento,
            idade = :idade,
            menor_idade = :menor_idade,
            sexo = :sexo,
            etnia = :etnia,
            responsavel_nome = :responsavel_nome,
            responsavel_cpf = :responsavel_cpf,
            endereco_completo = :endereco_completo,
            estado_civil = :estado_civil,
            com_quem_mora = :com_quem_mora,
            situacao_trabalho = :situacao_trabalho,
            renda_mensal = :renda_mensal,
            renda_familiar = :renda_familiar,
            cadastro_unico = :cadastro_unico,
            beneficios = :beneficios,
            problema_saude = :problema_saude,
            medicacao_continua = :medicacao_continua,
            acompanhamento_psicologico = :acompanhamento_psicologico,
            alergia = :alergia,
            possui_deficiencia = :possui_deficiencia,
            descricao_deficiencia = :descricao_deficiencia,
            filho_saude_alergia = :filho_saude_alergia,
            filho_medicacao = :filho_medicacao,
            refeicoes_dia = :refeicoes_dia,
            moradia = :moradia,
            saneamento_basico = :saneamento_basico,
            apoio_interesse = :apoio_interesse,
            dificuldades = :dificuldades,
            pode_oficina = :pode_oficina,
            rg_cpf = :rg_cpf,
            sugestao_pac = :sugestao_pac,
            perfil = 'pac',
            updated_at = NOW()
        WHERE id = :id
        RETURNING *;
        """,
        params,
    )


def excluir_cadastro_pac_admin(cadastro_id: int) -> dict | None:
    garantir_estrutura_pac()
    cadastro = execute_returning(
        """
        DELETE FROM cadastro.cadastro_pac
        WHERE id = :id
        RETURNING id, nome, cpf;
        """,
        {"id": cadastro_id},
    )
    if not cadastro:
        return None

    cpf = only_digits(cadastro.get("cpf"))
    if cpf:
        execute_command(
            """
            DELETE FROM cadastro._pac_criancas
            WHERE regexp_replace(COALESCE(crianca_cpf, ''), '[^0-9]', '', 'g') = :cpf;
            """,
            {"cpf": cpf},
        )
        execute_command(
            """
            UPDATE cadastro.cadastro_pac
            SET responsavel_nome = NULL,
                responsavel_cpf = NULL,
                updated_at = NOW()
            WHERE regexp_replace(COALESCE(responsavel_cpf, ''), '[^0-9]', '', 'g') = :cpf;
            """,
            {"cpf": cpf},
        )

    execute_command(
        """
        UPDATE atendimento.pac_solicitacoes
        SET cadastro_id = NULL,
            updated_at = NOW()
        WHERE cadastro_id = :id;
        """,
        {"id": cadastro_id},
    )
    sincronizar_pac_criancas()
    return cadastro


def sincronizar_pac_criancas() -> None:
    """Mantém cadastro._pac_criancas refletindo crianças PAC da tabela mestre."""
    from db.database import execute_command

    execute_command(
        """
        INSERT INTO cadastro._pac_criancas (crianca_cpf, crianca_nome)
        SELECT DISTINCT
            c.cpf AS crianca_cpf,
            c.nome AS crianca_nome
        FROM cadastro.cadastro_pac c
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
    return fetch_one(
        """
        SELECT *
        FROM cadastro.cadastro_pac
        WHERE regexp_replace(COALESCE(cpf, ''), '[^0-9]', '', 'g') = :cpf
        LIMIT 1;
        """,
        {"cpf": documento_limpo},
    )


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
    extra: dict | None = None,
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
    extra = extra or {}

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
        "nome_social": (extra.get("nome_social") or "").strip() or None,
        "endereco_completo": (extra.get("endereco_completo") or "").strip() or None,
        "estado_civil": (extra.get("estado_civil") or "").strip() or None,
        "com_quem_mora": (extra.get("com_quem_mora") or "").strip() or None,
        "situacao_trabalho": (extra.get("situacao_trabalho") or "").strip() or None,
        "renda_mensal": (extra.get("renda_mensal") or "").strip() or None,
        "renda_familiar": (extra.get("renda_familiar") or "").strip() or None,
        "cadastro_unico": (extra.get("cadastro_unico") or "").strip() or None,
        "beneficios": (extra.get("beneficios") or "").strip() or None,
        "problema_saude": (extra.get("problema_saude") or "").strip() or None,
        "medicacao_continua": (extra.get("medicacao_continua") or "").strip() or None,
        "acompanhamento_psicologico": (extra.get("acompanhamento_psicologico") or "").strip() or None,
        "alergia": (extra.get("alergia") or "").strip() or None,
        "filho_saude_alergia": (extra.get("filho_saude_alergia") or "").strip() or None,
        "filho_medicacao": (extra.get("filho_medicacao") or "").strip() or None,
        "refeicoes_dia": (extra.get("refeicoes_dia") or "").strip() or None,
        "moradia": (extra.get("moradia") or "").strip() or None,
        "saneamento_basico": (extra.get("saneamento_basico") or "").strip() or None,
        "apoio_interesse": (extra.get("apoio_interesse") or "").strip() or None,
        "dificuldades": (extra.get("dificuldades") or "").strip() or None,
        "pode_oficina": (extra.get("pode_oficina") or "").strip() or None,
        "rg_cpf": (extra.get("rg_cpf") or "").strip() or None,
        "sugestao_pac": (extra.get("sugestao_pac") or "").strip() or None,
    }

    if existente:
        cadastro = execute_returning(
            """
            UPDATE cadastro.cadastro_pac
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
                nome_social = :nome_social,
                endereco_completo = :endereco_completo,
                estado_civil = :estado_civil,
                com_quem_mora = :com_quem_mora,
                situacao_trabalho = :situacao_trabalho,
                renda_mensal = :renda_mensal,
                renda_familiar = :renda_familiar,
                cadastro_unico = :cadastro_unico,
                beneficios = :beneficios,
                problema_saude = :problema_saude,
                medicacao_continua = :medicacao_continua,
                acompanhamento_psicologico = :acompanhamento_psicologico,
                alergia = :alergia,
                filho_saude_alergia = :filho_saude_alergia,
                filho_medicacao = :filho_medicacao,
                refeicoes_dia = :refeicoes_dia,
                moradia = :moradia,
                saneamento_basico = :saneamento_basico,
                apoio_interesse = :apoio_interesse,
                dificuldades = :dificuldades,
                pode_oficina = :pode_oficina,
                rg_cpf = :rg_cpf,
                sugestao_pac = :sugestao_pac,
                updated_at = NOW(),
                participa_curso = COALESCE(participa_curso, false),
                perfil = CASE
                    WHEN perfil IS NULL OR TRIM(perfil) = '' THEN 'pac'
                    WHEN LOWER(perfil) = 'pac' THEN 'pac'
                    ELSE perfil
                END
            WHERE regexp_replace(COALESCE(cpf, ''), '[^0-9]', '', 'g') = :cpf
            RETURNING *;
            """,
            params,
        )
        sincronizar_pac_criancas()
        return {"acao": "atualizado", "cadastro": cadastro}

    cadastro = execute_returning(
        """
        INSERT INTO cadastro.cadastro_pac
        (
            nome, cpf, email, participa_curso, perfil, data_nascimento,
            idade, menor_idade, responsavel_nome, responsavel_cpf, telefone,
            sexo, possui_deficiencia, descricao_deficiencia, etnia, dados_compartilhamento,
            nome_social, endereco_completo, estado_civil, com_quem_mora,
            situacao_trabalho, renda_mensal, renda_familiar, cadastro_unico,
            beneficios, problema_saude, medicacao_continua, acompanhamento_psicologico,
            alergia, filho_saude_alergia, filho_medicacao, refeicoes_dia,
            moradia, saneamento_basico, apoio_interesse, dificuldades,
            pode_oficina, rg_cpf, sugestao_pac
        )
        VALUES
        (
            :nome, :cpf, :email, false, 'pac', :data_nascimento,
            :idade, :menor_idade, :responsavel_nome, :responsavel_cpf, :telefone,
            :sexo, :possui_deficiencia, :descricao_deficiencia, :etnia, :dados_compartilhamento,
            :nome_social, :endereco_completo, :estado_civil, :com_quem_mora,
            :situacao_trabalho, :renda_mensal, :renda_familiar, :cadastro_unico,
            :beneficios, :problema_saude, :medicacao_continua, :acompanhamento_psicologico,
            :alergia, :filho_saude_alergia, :filho_medicacao, :refeicoes_dia,
            :moradia, :saneamento_basico, :apoio_interesse, :dificuldades,
            :pode_oficina, :rg_cpf, :sugestao_pac
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
        extra=responsavel,
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
            extra={
                "problema_saude": filho.get("problema_saude"),
                "alergia": filho.get("alergia"),
                "medicacao_continua": filho.get("medicacao_continua"),
            },
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
        FROM cadastro.cadastro_pac
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
        INNER JOIN cadastro.cadastro_pac c
            ON c.cpf = pc.crianca_cpf
           AND LOWER(COALESCE(c.perfil, '')) = 'pac'
           AND COALESCE(c.idade, 999) < 18
        LEFT JOIN cadastro.cadastro_pac r
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
        FROM cadastro.cadastro_pac r
        LEFT JOIN cadastro.cadastro_pac c
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
        INNER JOIN cadastro.cadastro_pac c
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
        INNER JOIN cadastro.cadastro_pac c
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
            FROM cadastro.cadastro_pac
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
