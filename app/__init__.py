from __future__ import annotations

import os
from flask import Flask
from dotenv import load_dotenv


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    from app.routes.user import bp as user_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.api import bp as api_bp
    from app.routes.assinaturas import bp as assinaturas_bp
    from app.routes.admin_pac import bp as admin_pac_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(admin_pac_bp, url_prefix="/admin-pac")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(assinaturas_bp)

    @app.template_filter("brl")
    def brl(value):
        from services.financeiro_service import format_brl_value
        try:
            return format_brl_value(value)
        except Exception:
            return "R$ 0,00"

    @app.template_filter("datebr")
    def datebr(value):
        import pandas as pd
        if value is None or str(value) in {"NaT", "nan", "None"}:
            return "-"
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return str(value)
        return dt.strftime("%d/%m/%Y")

    @app.template_filter("datetimebr")
    def datetimebr(value):
        import pandas as pd
        if value is None or str(value) in {"NaT", "nan", "None"}:
            return "-"
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return str(value)
        return dt.strftime("%d/%m/%Y %H:%M")

    return app
