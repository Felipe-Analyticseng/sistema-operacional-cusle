import os
import hmac
from dotenv import load_dotenv

load_dotenv()


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
        users[single_user.strip()] = single_password.strip()

    multi_users = os.getenv("ADMIN_USERS", "")
    if multi_users:
        for item in multi_users.split(","):
            if ":" not in item:
                continue

            username, password = item.split(":", 1)
            username = username.strip()
            password = password.strip()

            if username and password:
                users[username] = password

    return users


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

    usuario_limpo = usuario.strip()
    senha_esperada = users.get(usuario_limpo)

    if not senha_esperada:
        return None

    if not hmac.compare_digest(str(senha), str(senha_esperada)):
        return None

    nome = usuario_limpo.split("@")[0]

    return {
        "nome": nome,
        "email": usuario_limpo,
    }