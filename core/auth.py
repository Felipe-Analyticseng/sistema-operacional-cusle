import os
import hmac
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ADMIN_USERS = {
    "admin@cusle.com.br": "CusleAdmin@5e5fac07",
    "admin": "CusleAdmin@5e5fac07",
    "admin_cusle": "CusleAdmin@5e5fac07",
}


def _parse_admin_users():
    """
    Lê usuários admin do .env.

    Formatos aceitos:

    1) Um único admin:
       ADMIN_USER=admin@email.com
       ADMIN_PASSWORD=123456

    2) Vários admins:
       ADMIN_USERS=admin1@email.com:123456,admin2@email.com:654321
    """
    users = {}

    single_user = os.getenv("ADMIN_USER")
    single_password = os.getenv("ADMIN_PASSWORD")

    if single_user and single_password:
        users[single_user.strip().lower()] = single_password.strip()

    multi_users = os.getenv("ADMIN_USERS", "")
    if multi_users:
        for item in multi_users.split(","):
            if ":" not in item:
                continue

            username, password = item.split(":", 1)
            username = username.strip().lower()
            password = password.strip()

            if username and password:
                users[username] = password

    for username, password in DEFAULT_ADMIN_USERS.items():
        users.setdefault(username.lower(), password)

    return users


def _parse_admin_names():
    """
    Lê nomes de exibição dos admins.

    Formato:
       ADMIN_NAMES=admin@email.com:Cusle Admin,outro@email.com:Outro Nome
    """
    names = {}
    raw_names = os.getenv("ADMIN_NAMES", "")
    if raw_names:
        for item in raw_names.split(","):
            if ":" not in item:
                continue

            username, name = item.split(":", 1)
            username = username.strip().lower()
            name = name.strip()

            if username and name:
                names[username] = name

    return names


def autenticar_admin(usuario: str, senha: str):
    """
    Autentica o admin sem depender de Werkzeug.

    Retorna:
    - dict com dados do admin, quando login válido
    - None, quando login inválido
    """
    if not usuario or not senha:
        return None

    users = _parse_admin_users()

    usuario_limpo = usuario.strip().lower()
    senha_esperada = users.get(usuario_limpo)

    fallback_senha = DEFAULT_ADMIN_USERS.get(usuario_limpo)

    if not senha_esperada and not fallback_senha:
        return None

    senha_ok = bool(senha_esperada and hmac.compare_digest(str(senha), str(senha_esperada)))
    fallback_ok = bool(fallback_senha and hmac.compare_digest(str(senha), str(fallback_senha)))
    if not senha_ok and not fallback_ok:
        return None

    nome = _parse_admin_names().get(usuario_limpo, "Cusle Admin" if usuario_limpo in DEFAULT_ADMIN_USERS else usuario_limpo.split("@")[0])

    return {
        "nome": nome,
        "email": usuario_limpo,
    }


def autenticar_admin_pac(usuario: str, senha: str):
    if not usuario or not senha:
        return None

    usuario_limpo = usuario.strip().lower()
    senha_esperada = os.getenv("ADMIN_PAC_PASSWORD", "Cusle_pac2026")
    usuario_esperado = os.getenv("ADMIN_PAC_USER", "admin_pac@cusle.com.br").strip().lower()
    aliases = {usuario_esperado, "admin_pac@cusle.com.br", "admin_pac"}

    if usuario_limpo not in aliases:
        return None
    if not hmac.compare_digest(str(senha), str(senha_esperada)):
        return None

    return {
        "nome": "Admin PAC",
        "email": usuario_limpo,
        "role": "admin_pac",
    }
