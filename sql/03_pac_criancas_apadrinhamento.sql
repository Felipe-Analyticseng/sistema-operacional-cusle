-- =========================================================
-- PAC - Programa Acolhe CUSLE
-- Estrutura incremental e segura para cadastro.cadastro
-- =========================================================

CREATE SCHEMA IF NOT EXISTS cadastro;
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

CREATE TABLE IF NOT EXISTS cadastro._pac_criancas (
    id SERIAL PRIMARY KEY,
    crianca_cpf VARCHAR(20) NOT NULL UNIQUE,
    crianca_nome VARCHAR(200) NOT NULL,
    padrinho_cpf VARCHAR(20),
    padrinho_nome VARCHAR(200),
    data_apadrinhamento TIMESTAMP WITH TIME ZONE
);

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
