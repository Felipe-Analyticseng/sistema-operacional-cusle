CREATE SCHEMA IF NOT EXISTS cadastro;

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

CREATE TABLE IF NOT EXISTS cadastro.envelopes (
    id SERIAL PRIMARY KEY,
    doc_key VARCHAR(60) NOT NULL,
    cadastro_id INTEGER NOT NULL,
    token VARCHAR(200) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    signed_pdf_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    signed_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_envelope_doc_cadastro
    ON cadastro.envelopes (doc_key, cadastro_id);
