from __future__ import annotations

from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from config.settings import BASE_DIR
from core.auth import autenticar_admin_pac
from db.database import execute_returning, fetch_one
from services.assinatura_service import historico_assinaturas
from services.pac_service import (
    listar_criancas_pac,
    listar_filhos_por_responsavel,
    listar_pac_cadastros,
    listar_responsaveis_pac,
)
from app.routes.admin import _pac_summary
from app.routes.helpers import admin_pac_required, df_records, excel_response

bp = Blueprint("admin_pac", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin = autenticar_admin_pac(request.form.get("usuario"), request.form.get("senha"))
        if admin:
            session["admin_pac_logado"] = True
            session["admin_pac"] = admin
            flash("Login PAC realizado com sucesso.", "success")
            return redirect(url_for("admin_pac.dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin_pac/login.html")


@bp.get("/logout")
def logout():
    session.pop("admin_pac_logado", None)
    session.pop("admin_pac", None)
    flash("Sessão PAC encerrada.", "success")
    return redirect(url_for("admin_pac.login"))


@bp.get("/")
@admin_pac_required
def dashboard():
    cadastros = listar_pac_cadastros()
    criancas = listar_criancas_pac()
    responsaveis = listar_responsaveis_pac()
    cpf = request.args.get("cpf")
    filhos = listar_filhos_por_responsavel(cpf) if cpf else None
    return render_template(
        "admin_pac/dashboard.html",
        cadastros=df_records(cadastros),
        criancas=df_records(criancas),
        responsaveis=df_records(responsaveis),
        filhos=df_records(filhos),
        selected_cpf=cpf,
        resumo=_pac_summary(cadastros, criancas),
        assinaturas=historico_assinaturas("pac_batch"),
    )


@bp.get("/pessoa/<int:cadastro_id>")
@admin_pac_required
def pessoa(cadastro_id: int):
    pessoa = fetch_one("SELECT * FROM cadastro.cadastro_pac WHERE id = :id LIMIT 1;", {"id": cadastro_id})
    if not pessoa:
        flash("Pessoa PAC não encontrada.", "danger")
        return redirect(url_for("admin_pac.dashboard"))
    return render_template("admin_pac/pessoa.html", pessoa=pessoa)


@bp.post("/pessoa/<int:cadastro_id>/foto")
@admin_pac_required
def pessoa_foto(cadastro_id: int):
    arquivo = request.files.get("foto")
    if not arquivo or not arquivo.filename:
        flash("Selecione uma foto para anexar.", "warning")
        return redirect(url_for("admin_pac.pessoa", cadastro_id=cadastro_id))

    ext = Path(arquivo.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        flash("Formato de foto inválido. Use JPG, PNG ou WEBP.", "danger")
        return redirect(url_for("admin_pac.pessoa", cadastro_id=cadastro_id))

    upload_dir = BASE_DIR / "uploads" / "pac_fotos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(f"pac_{cadastro_id}{ext}")
    path = upload_dir / filename
    arquivo.save(path)
    execute_returning(
        """
        UPDATE cadastro.cadastro_pac
        SET foto_path = :foto_path, updated_at = NOW()
        WHERE id = :id
        RETURNING id;
        """,
        {"id": cadastro_id, "foto_path": str(path)},
    )
    flash("Foto anexada com sucesso.", "success")
    return redirect(url_for("admin_pac.pessoa", cadastro_id=cadastro_id))


@bp.get("/foto/<int:cadastro_id>")
@admin_pac_required
def foto(cadastro_id: int):
    pessoa = fetch_one("SELECT foto_path FROM cadastro.cadastro_pac WHERE id = :id LIMIT 1;", {"id": cadastro_id})
    path = Path(str((pessoa or {}).get("foto_path") or ""))
    if not path.exists() or not path.is_file():
        return redirect(url_for("static", filename="img/logo_cusle.png"))
    return send_file(path, as_attachment=False)


@bp.get("/export/<kind>")
@admin_pac_required
def export(kind: str):
    if kind == "responsaveis":
        return excel_response(listar_responsaveis_pac(), "pac_maes_responsaveis.xlsx")
    if kind == "criancas":
        return excel_response(listar_criancas_pac(), "pac_criancas.xlsx")
    return excel_response(listar_pac_cadastros(), "pac_cadastros.xlsx")
