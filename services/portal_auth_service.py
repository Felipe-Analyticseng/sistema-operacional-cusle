from __future__ import annotations

from typing import Literal

from werkzeug.security import check_password_hash, generate_password_hash

from db.database import execute_command, execute_returning, fetch_one, run_query
from services.cadastro_service import buscar_cadastro_por_cpf, only_digits
from core.auth import autenticar_admin

APPROVED = "aprovado"
PENDING = "pendente"
REJECTED = "reprovado"


def ensure_portal_tables() -> None:
    """Cria a estrutura de usuários do portal sem alterar tabelas existentes."""
    execute_command("CREATE SCHEMA IF NOT EXISTS cadastro;")
    execute_command(
        """
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
        """
    )
    execute_command(
        """
        CREATE INDEX IF NOT EXISTS idx_portal_users_cpf
            ON cadastro.portal_users (cpf);
        """
    )
    execute_command(
        """
        CREATE INDEX IF NOT EXISTS idx_portal_users_status
            ON cadastro.portal_users (status);
        """
    )


def _cadastro_snapshot(cpf: str | None) -> dict:
    cadastro = buscar_cadastro_por_cpf(cpf or "")
    return {
        "cadastro_id": cadastro.get("id") if cadastro else None,
        "nome": cadastro.get("nome") if cadastro else None,
        "perfil": cadastro.get("perfil") if cadastro else None,
    }


def registrar_usuario_portal(email: str, cpf: str, senha: str, confirmar_senha: str) -> dict:
    ensure_portal_tables()
    email_limpo = (email or "").strip().lower()
    cpf_limpo = only_digits(cpf)

    if not email_limpo:
        raise ValueError("Informe seu e-mail.")
    if not cpf_limpo:
        raise ValueError("Informe seu CPF.")
    if not senha or len(senha) < 6:
        raise ValueError("Crie uma senha com pelo menos 6 caracteres.")
    if senha != confirmar_senha:
        raise ValueError("A confirmação de senha não confere.")

    existente = fetch_one(
        "SELECT id, status FROM cadastro.portal_users WHERE LOWER(email) = :email LIMIT 1;",
        {"email": email_limpo},
    )
    if existente:
        raise ValueError("Já existe uma solicitação para este e-mail. Consulte o status ou tente fazer login.")

    cadastro = _cadastro_snapshot(cpf_limpo)
    return execute_returning(
        """
        INSERT INTO cadastro.portal_users
            (cadastro_id, nome, perfil, cpf, email, password_hash, status)
        VALUES
            (:cadastro_id, :nome, :perfil, :cpf, :email, :password_hash, 'pendente')
        RETURNING id, nome, perfil, cpf, email, status, created_at;
        """,
        {
            **cadastro,
            "cpf": cpf_limpo,
            "email": email_limpo,
            "password_hash": generate_password_hash(senha),
        },
    )


def buscar_status_portal(email: str | None = None, cpf: str | None = None) -> dict | None:
    ensure_portal_tables()
    email_limpo = (email or "").strip().lower()
    cpf_limpo = only_digits(cpf)

    if not email_limpo and not cpf_limpo:
        return None

    row = fetch_one(
        """
        SELECT
            pu.id,
            COALESCE(c.nome, pu.nome) AS nome,
            COALESCE(c.perfil, pu.perfil) AS perfil,
            pu.cpf,
            pu.email,
            pu.status,
            pu.observacao_admin,
            pu.created_at,
            pu.updated_at
        FROM cadastro.portal_users pu
        LEFT JOIN cadastro.cadastro c
            ON c.cpf = pu.cpf
        WHERE (:email IS NOT NULL AND LOWER(pu.email) = :email)
           OR (:cpf IS NOT NULL AND pu.cpf = :cpf)
        ORDER BY pu.created_at DESC
        LIMIT 1;
        """,
        {"email": email_limpo or None, "cpf": cpf_limpo},
    )
    if row:
        return row

    cadastro = buscar_cadastro_por_cpf(cpf_limpo or "") if cpf_limpo else None
    if cadastro:
        return {
            "nome": cadastro.get("nome"),
            "perfil": cadastro.get("perfil"),
            "cpf": cpf_limpo,
            "email": email_limpo,
            "status": "sem_solicitacao",
            "observacao_admin": None,
        }

    return {
        "nome": None,
        "perfil": None,
        "cpf": cpf_limpo,
        "email": email_limpo,
        "status": "sem_cadastro",
        "observacao_admin": None,
    }


def mensagem_status_portal(row: dict | None) -> str:
    if not row:
        return "Favor realizar o registro e aguardar aprovação do administrador."
    status = str(row.get("status") or "").lower()

    if status == PENDING:
        return "Aguardando aprovação do administrador."
    if status == REJECTED:
        return "Cadastro não aprovado, entre em contato com o administrador."
    if status in {"sem_cadastro", "sem_solicitacao"}:
        return "Favor realizar o registro e aguardar aprovação do administrador."
    return "Status localizado."


def autenticar_usuario_portal(email: str, senha: str) -> dict | None:
    ensure_portal_tables()
    email_limpo = (email or "").strip().lower()
    if not email_limpo or not senha:
        return None

    # Admin acessa automaticamente o portal, mas continua usando o login admin para o painel admin.
    admin = autenticar_admin(email_limpo, senha)
    if admin:
        return {"id": None, "nome": admin["nome"], "email": admin["email"], "cpf": None, "perfil": "admin", "is_admin": True}

    row = fetch_one(
        """
        SELECT
            pu.id,
            COALESCE(c.nome, pu.nome) AS nome,
            COALESCE(c.perfil, pu.perfil) AS perfil,
            pu.cpf,
            pu.email,
            pu.password_hash,
            pu.status
        FROM cadastro.portal_users pu
        LEFT JOIN cadastro.cadastro c
            ON c.cpf = pu.cpf
        WHERE LOWER(pu.email) = :email
        LIMIT 1;
        """,
        {"email": email_limpo},
    )
    if not row or not check_password_hash(row.get("password_hash") or "", senha):
        return None

    if row.get("status") != APPROVED:
        return None

    return {"id": row["id"], "nome": row.get("nome"), "email": row["email"], "cpf": row.get("cpf"), "perfil": row.get("perfil"), "is_admin": False}


def listar_solicitacoes_portal():
    ensure_portal_tables()
    return run_query(
        """
        SELECT
            pu.id,
            COALESCE(c.nome, pu.nome) AS nome,
            COALESCE(c.perfil, pu.perfil) AS perfil,
            pu.cpf,
            pu.email,
            pu.status,
            pu.observacao_admin,
            pu.created_at,
            pu.updated_at
        FROM cadastro.portal_users pu
        LEFT JOIN cadastro.cadastro c
            ON c.cpf = pu.cpf
        ORDER BY
            CASE pu.status
                WHEN 'pendente' THEN 1
                WHEN 'aprovado' THEN 2
                WHEN 'reprovado' THEN 3
                ELSE 4
            END,
            pu.created_at DESC;
        """
    )


def atualizar_status_usuario_portal(user_id: int, status: Literal["pendente", "aprovado", "reprovado"], observacao_admin: str | None, admin_email: str | None) -> dict:
    ensure_portal_tables()
    if status not in {PENDING, APPROVED, REJECTED}:
        raise ValueError("Status inválido para usuário do portal.")

    current = fetch_one(
        """
        SELECT pu.cpf, c.id AS cadastro_id, c.nome, c.perfil
        FROM cadastro.portal_users pu
        LEFT JOIN cadastro.cadastro c
            ON c.cpf = pu.cpf
        WHERE pu.id = :user_id
        LIMIT 1;
        """,
        {"user_id": user_id},
    )
    if not current:
        raise ValueError("Usuário não encontrado.")

    return execute_returning(
        """
        UPDATE cadastro.portal_users
        SET
            cadastro_id = :cadastro_id,
            nome = :nome,
            perfil = :perfil,
            status = :status,
            observacao_admin = :observacao_admin,
            approved_by = CASE WHEN :status = 'aprovado' THEN :admin_email ELSE approved_by END,
            approved_at = CASE WHEN :status = 'aprovado' THEN NOW() ELSE approved_at END,
            updated_at = NOW()
        WHERE id = :user_id
        RETURNING id, nome, perfil, cpf, email, status, observacao_admin, updated_at;
        """,
        {
            "user_id": user_id,
            "cadastro_id": current.get("cadastro_id"),
            "nome": current.get("nome"),
            "perfil": current.get("perfil"),
            "status": status,
            "observacao_admin": observacao_admin.strip() if observacao_admin else None,
            "admin_email": admin_email,
        },
    )
