# db/database.py

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError


# Carrega o .env de forma explícita a partir da raiz do projeto.
# Isso evita problema quando o app é iniciado a partir de outro diretório.
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL não encontrada. Confira se existe um arquivo .env na raiz do projeto, "
        "na mesma pasta do wsgi.py."
    )

# Compatibilidade com URLs antigas do Render/Heroku.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _is_local_database(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host in {"localhost", "127.0.0.1"} or host.startswith("192.168.")


def _build_connect_args(url: str) -> dict[str, Any]:
    """
    Para banco externo do Render, forçamos SSL quando a URL ainda não trouxe sslmode.
    Se a URL já vier com ?sslmode=require, não duplicamos nada.
    """
    if "sslmode=" in url.lower():
        return {}

    if _is_local_database(url):
        return {}

    return {"sslmode": "require"}


def _safe_db_label(url: str) -> str:
    """Mostra dados não sensíveis para debug, sem expor senha."""
    parsed = urlparse(url)
    return (
        f"driver={parsed.scheme}, "
        f"user={parsed.username}, "
        f"host={parsed.hostname}, "
        f"port={parsed.port or 5432}, "
        f"database={(parsed.path or '').lstrip('/')}"
    )


engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    connect_args=_build_connect_args(DATABASE_URL),
)


def test_connection() -> bool:
    """
    Teste simples para validar se o Flask consegue abrir conexão com o PostgreSQL.
    Pode ser usado no terminal com:
    python -c "from db.database import test_connection; test_connection()"
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(text("select current_database(), current_user")).fetchone()
            print("Conexão OK:", row)
            return True
    except OperationalError as exc:
        print("Falha ao conectar no banco.")
        print("Configuração lida:", _safe_db_label(DATABASE_URL))
        print("Erro original:", repr(getattr(exc, "orig", exc)))
        return False


def run_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Executa SELECT e retorna o resultado como DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict | None:
    """Executa SELECT e retorna apenas um registro como dicionário."""
    with engine.connect() as conn:
        row = conn.execute(text(query), params or {}).mappings().first()
        return dict(row) if row else None


def execute_command(query: str, params: dict[str, Any] | None = None) -> None:
    """Executa INSERT, UPDATE, DELETE ou comandos DDL."""
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def execute_returning(query: str, params: dict[str, Any] | None = None) -> dict | None:
    """Executa INSERT/UPDATE com RETURNING e retorna o registro afetado."""
    with engine.begin() as conn:
        row = conn.execute(text(query), params or {}).mappings().first()
        return dict(row) if row else None
