-- 04_portal_users.sql
-- Estrutura para autorização de usuários do Portal CUSLE.
-- Observação: no PostgreSQL o caminho correto usa duas partes: schema.tabela.
-- Por isso foi criada a tabela cadastro.portal_users para representar cadastro.portal.users.

CREATE SCHEMA IF NOT EXISTS cadastro;

CREATE TABLE IF NOT EXISTS cadastro.portal_users (
    id SERIAL PRIMARY KEY,
    cadastro_id INTEGER NULL,
    nome VARCHAR(200),
    perfil VARCHAR(80),
    cpf VARCHAR(20) NOT NULL,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pendente',
    observacao_admin TEXT,
    approved_by VARCHAR(200),
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_users_cpf
    ON cadastro.portal_users (cpf);

CREATE INDEX IF NOT EXISTS idx_portal_users_status
    ON cadastro.portal_users (status);
