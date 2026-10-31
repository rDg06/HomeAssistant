"""Palavra-passe única da casa: protege todas as páginas da app."""
import time

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/entrar")

MINIMO = 6  # caracteres
PAGINAS_LIVRES = {"auth.entrar", "auth.definir", "static"}


def _hash_guardado():
    linha = get_db().execute("SELECT valor FROM definicoes WHERE chave = 'passe'").fetchone()
    return linha[0] if linha else None


def _guardar_hash(passe):
    novo = generate_password_hash(passe)
    db = get_db()
    db.execute("INSERT OR REPLACE INTO definicoes (chave, valor) VALUES ('passe', ?)", (novo,))
    db.commit()
    return novo


def _iniciar_sessao(hash_atual):
    session.clear()
    session.permanent = True
    # Guardar parte do hash faz com que mudar a palavra-passe termine as sessões abertas noutros aparelhos.
    session["passe"] = hash_atual[-16:]


def _destino_seguro(destino):
    """Só deixa voltar a páginas desta app (nunca a outro site)."""
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return url_for("inicio")


def proteger():
    """Corre antes de cada pedido: quem não entrou é enviado para a página de entrada."""
    if request.endpoint in PAGINAS_LIVRES or request.endpoint is None:
        return None
    hash_atual = _hash_guardado()
    if hash_atual is None:
        return redirect(url_for("auth.definir"))
    if session.get("passe") == hash_atual[-16:]:
        return None
    if request.is_json:
        abort(401)
    seguinte = request.full_path.rstrip("?") if request.method == "GET" else None
    return redirect(url_for("auth.entrar", seguinte=seguinte))


@bp.route("/", methods=["GET", "POST"])
def entrar():
    hash_atual = _hash_guardado()
    if hash_atual is None:
        return redirect(url_for(".definir"))
    seguinte = request.values.get("seguinte", "")
    if request.method == "POST":
        if check_password_hash(hash_atual, request.form.get("passe", "")):
            _iniciar_sessao(hash_atual)
            return redirect(_destino_seguro(seguinte))
        time.sleep(1)  # torna mais lento tentar adivinhar
        flash("Palavra-passe errada.", "erro")
    return render_template("auth/entrar.html", seguinte=seguinte)


@bp.route("/definir", methods=["GET", "POST"])
def definir():
    """Só funciona enquanto ainda não houver palavra-passe (primeira vez ou depois de a repor)."""
    if _hash_guardado() is not None:
        return redirect(url_for(".entrar"))
    if request.method == "POST":
        passe = request.form.get("passe", "")
        if len(passe) < MINIMO:
            flash(f"A palavra-passe tem de ter pelo menos {MINIMO} caracteres.", "erro")
        elif passe != request.form.get("confirmar", ""):
            flash("As duas palavras-passe não são iguais.", "erro")
        else:
            _iniciar_sessao(_guardar_hash(passe))
            flash("Palavra-passe criada. A partir de agora a app pede-a para entrar.", "ok")
            return redirect(url_for("inicio"))
    return render_template("auth/definir.html", minimo=MINIMO)


@bp.route("/mudar", methods=["GET", "POST"])
def mudar():
    if request.method == "POST":
        f = request.form
        if not check_password_hash(_hash_guardado(), f.get("atual", "")):
            time.sleep(1)
            flash("A palavra-passe atual está errada.", "erro")
        elif len(f.get("nova", "")) < MINIMO:
            flash(f"A nova palavra-passe tem de ter pelo menos {MINIMO} caracteres.", "erro")
        elif f.get("nova") != f.get("confirmar"):
            flash("As duas palavras-passe novas não são iguais.", "erro")
        else:
            _iniciar_sessao(_guardar_hash(f["nova"]))
            flash("Palavra-passe mudada. Os outros aparelhos vão ter de entrar outra vez.", "ok")
            return redirect(url_for("inicio"))
    return render_template("auth/mudar.html", minimo=MINIMO)


@bp.post("/sair")
def sair():
    session.clear()
    return redirect(url_for(".entrar"))


def repor_passe(app):
    """Apaga a palavra-passe (para quando é esquecida). Na próxima visita a app pede uma nova."""
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM definicoes WHERE chave = 'passe'")
        db.commit()
