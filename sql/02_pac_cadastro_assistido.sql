-- 02_pac_cadastro_assistido.sql
-- Ajustes incrementais para o PAC sem remover ou renomear colunas existentes.

CREATE SCHEMA IF NOT EXISTS atendimento;

ALTER TABLE cadastro.cadastro
    ADD COLUMN IF NOT EXISTS idade INTEGER,
    ADD COLUMN IF NOT EXISTS sexo VARCHAR(30),
    ADD COLUMN IF NOT EXISTS possui_deficiencia BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS descricao_deficiencia TEXT,
    ADD COLUMN IF NOT EXISTS etnia VARCHAR(30),
    ADD COLUMN IF NOT EXISTS dados_compartilhamento BOOLEAN DEFAULT FALSE;

UPDATE cadastro.cadastro
SET idade = DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT
WHERE data_nascimento IS NOT NULL
  AND (idade IS NULL OR idade <> DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))::INT);

CREATE TABLE IF NOT EXISTS atendimento.pac_apadrinhamentos (
    id SERIAL PRIMARY KEY,
    padrinho_cadastro_id INTEGER NOT NULL,
    crianca_cadastro_id INTEGER NOT NULL,
    padrinho_nome VARCHAR(200),
    padrinho_cpf VARCHAR(20),
    crianca_nome VARCHAR(200),
    crianca_documento VARCHAR(20),
    status VARCHAR(30) NOT NULL DEFAULT 'ativo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_pac_crianca_apadrinhamento UNIQUE (crianca_cadastro_id)
);

CREATE OR REPLACE VIEW atendimento.pac_criancas AS
SELECT
    c.id AS cadastro_id,
    c.nome,
    c.cpf,
    c.idade,
    c.sexo,
    c.etnia,
    c.possui_deficiencia,
    c.descricao_deficiencia,
    c.responsavel_nome,
    c.responsavel_cpf,
    r.telefone AS responsavel_telefone,
    r.email AS responsavel_email,
    CASE WHEN a.id IS NULL THEN 'não apadrinhada' ELSE 'apadrinhada' END AS apadrinhamento,
    a.padrinho_nome,
    a.created_at AS data_apadrinhamento
FROM cadastro.cadastro c
LEFT JOIN cadastro.cadastro r
    ON r.cpf = c.responsavel_cpf
LEFT JOIN atendimento.pac_apadrinhamentos a
    ON a.crianca_cadastro_id = c.id
   AND a.status = 'ativo'
WHERE LOWER(COALESCE(c.perfil, '')) = 'pac'
  AND COALESCE(c.idade, 999) < 18;
