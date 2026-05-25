CREATE SCHEMA IF NOT EXISTS atendimento;

CREATE TABLE IF NOT EXISTS atendimento.comprovantes (
    id SERIAL PRIMARY KEY,
    cadastro_id INTEGER NULL,
    nome_informado VARCHAR(200) NOT NULL,
    cpf_informado VARCHAR(20),
    telefone_informado VARCHAR(30),
    tipo_comprovante VARCHAR(80) NOT NULL,
    mes_referencia VARCHAR(7),
    valor_informado NUMERIC(12,2),
    justificativa TEXT,
    arquivo_path TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'pendente',
    observacao_admin TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.limpeza_registros (
    id SERIAL PRIMARY KEY,
    cadastro_id INTEGER NULL,
    nome_informado VARCHAR(200) NOT NULL,
    cpf_informado VARCHAR(20),
    data_faxina DATE NOT NULL,
    observacao TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.calendario_giras (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    tipo_gira VARCHAR(100),
    data_gira DATE NOT NULL,
    horario VARCHAR(20),
    descricao TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.conteudos_informativos (
    id SERIAL PRIMARY KEY,
    categoria VARCHAR(100) NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    conteudo TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.pac_solicitacoes (
    id SERIAL PRIMARY KEY,
    cadastro_id INTEGER NULL,
    nome_informado VARCHAR(200),
    cpf_informado VARCHAR(20),
    telefone_informado VARCHAR(30),
    tipo_solicitacao VARCHAR(80) NOT NULL,
    descricao TEXT,
    status VARCHAR(30) DEFAULT 'novo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.chat_sessions (
    id SERIAL PRIMARY KEY,
    canal VARCHAR(30) NOT NULL,
    user_identifier VARCHAR(200),
    estado_atual VARCHAR(100),
    ultimo_menu VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS atendimento.chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES atendimento.chat_sessions(id),
    canal VARCHAR(30) NOT NULL,
    direcao VARCHAR(30) NOT NULL,
    mensagem TEXT,
    payload_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);