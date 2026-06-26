from __future__ import annotations

from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from config.settings import BASE_DIR
from core.auth import autenticar_admin_pac
from db.database import execute_returning, fetch_one
from services.assinatura_service import historico_assinaturas
from services.cursos_service import listar_cursos_pac_com_inscritos, listar_inscritos_curso_pac
from services.pac_service import (
    PAC_EDIT_FIELDS,
    atualizar_cadastro_pac_admin,
    excluir_cadastro_pac_admin,
    listar_criancas_pac,
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
    return render_template(
        "admin_pac/dashboard.html",
        cadastros=df_records(cadastros),
        criancas=df_records(criancas),
        resumo=_pac_summary(cadastros, criancas),
    )


@bp.get("/assinaturas")
@admin_pac_required
def assinaturas():
    status = (request.args.get("status") or "").strip()
    assinaturas = historico_assinaturas("pac_batch")
    if status:
        assinaturas = [item for item in assinaturas if item.get("status") == status]
    return render_template(
        "admin_pac/assinaturas.html",
        assinaturas=assinaturas,
        selected_status=status,
    )


@bp.get("/cursos")
@admin_pac_required
def cursos():
    return render_template("admin_pac/cursos.html", cursos=listar_cursos_pac_com_inscritos())


@bp.get("/cursos/<curso_key>/export")
@admin_pac_required
def cursos_export(curso_key: str):
    filename = f"pac_curso_{curso_key.lower()}.xlsx"
    return excel_response(listar_inscritos_curso_pac(curso_key), filename)


@bp.get("/pessoa/<int:cadastro_id>")
@admin_pac_required
def pessoa(cadastro_id: int):
    pessoa = fetch_one("SELECT * FROM cadastro.cadastro_pac WHERE id = :id LIMIT 1;", {"id": cadastro_id})
    if not pessoa:
        flash("Pessoa PAC não encontrada.", "danger")
        return redirect(url_for("admin_pac.dashboard"))
    return render_template("admin_pac/pessoa.html", pessoa=pessoa, edit_fields=PAC_EDIT_FIELDS)


@bp.post("/pessoa/<int:cadastro_id>")
@admin_pac_required
def pessoa_update(cadastro_id: int):
    try:
        atualizado = atualizar_cadastro_pac_admin(cadastro_id, request.form)
        if not atualizado:
            flash("Pessoa PAC nao encontrada.", "danger")
            return redirect(url_for("admin_pac.dashboard"))
        flash("Alteracoes salvas com sucesso.", "success")
    except Exception as exc:
        flash(str(exc), "danger")
    return redirect(url_for("admin_pac.pessoa", cadastro_id=cadastro_id))


@bp.post("/pessoa/<int:cadastro_id>/excluir")
@admin_pac_required
def pessoa_delete(cadastro_id: int):
    try:
        excluido = excluir_cadastro_pac_admin(cadastro_id)
        if not excluido:
            flash("Pessoa PAC nao encontrada.", "danger")
            return redirect(url_for("admin_pac.dashboard"))
        flash(f"Cadastro PAC de {excluido.get('nome')} excluido com sucesso.", "success")
    except Exception as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin_pac.pessoa", cadastro_id=cadastro_id))
    return redirect(url_for("admin_pac.dashboard"))


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
