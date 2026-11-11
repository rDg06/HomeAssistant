"""Página de configurações: pastas das cópias de segurança e palavra-passe."""
import os
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from . import auth, backup

bp = Blueprint("configuracoes", __name__, url_prefix="/configuracoes")


def _voltar(ancora="copias"):
    return redirect(url_for(".pagina", _anchor=ancora))


@bp.route("/")
def pagina():
    app = current_app._get_current_object()
    ficheiro = os.path.join(app.instance_path, backup.FICHEIRO_PASTAS)
    return render_template(
        "configuracoes.html",
        pastas=[backup.estado(p) for p in backup.pastas(app)],
        por_defeito=not backup.pastas_da_variavel() and not os.path.exists(ficheiro),
        da_variavel=backup.pastas_da_variavel(),
        dias=backup.DIAS_ENTRE_COPIAS,
        manter=backup.COPIAS_A_MANTER,
        minimo=auth.MINIMO,
        agora=datetime.now(),
    )


@bp.post("/pastas/adicionar")
def adicionar_pasta():
    app = current_app._get_current_object()
    pasta = request.form.get("pasta", "").strip().strip('"')
    if backup.pastas_da_variavel():
        flash("As pastas estão definidas na variável CASA_BACKUPS e não podem ser mudadas aqui.", "erro")
        return _voltar()
    if not pasta:
        flash("Escreve o caminho da pasta.", "erro")
        return _voltar()
    if os.path.isabs(pasta):
        pasta = os.path.abspath(pasta)
    problema = backup.problema_na_pasta(pasta)
    if problema:
        flash(problema, "erro")
        return _voltar()
    # Junta-se às pastas atuais (a primeira escolhida fica ao lado da pasta por defeito, que continua a ter cópias).
    atuais = backup.pastas(app)
    if os.path.normcase(pasta) in map(os.path.normcase, atuais):
        flash("Essa pasta já está na lista.", "erro")
        return _voltar()
    backup.guardar_pastas(app, atuais + [pasta])
    flash(f"Pasta adicionada: {pasta}. Carrega em \"Fazer cópia agora\" para a primeira cópia.", "ok")
    return _voltar()


@bp.post("/pastas/remover")
def remover_pasta():
    app = current_app._get_current_object()
    pasta = request.form.get("pasta", "")
    if backup.pastas_da_variavel():
        flash("As pastas estão definidas na variável CASA_BACKUPS e não podem ser mudadas aqui.", "erro")
        return _voltar()
    restantes = [p for p in backup.pastas(app) if os.path.normcase(p) != os.path.normcase(pasta)]
    backup.guardar_pastas(app, restantes)
    if restantes:
        flash(f"Pasta tirada da lista: {pasta}. As cópias que lá estão não foram apagadas.", "ok")
    else:
        flash("Sem pastas escolhidas, as cópias voltam a ser feitas na pasta por defeito.", "ok")
    return _voltar()


@bp.post("/copia-agora")
def copia_agora():
    resultados = backup.fazer_copia(current_app._get_current_object())
    feitas = [p for p, _, erro in resultados if not erro]
    falhas = [f"{p} ({erro})" for p, _, erro in resultados if erro]
    if feitas:
        flash(f"Cópia feita em {len(feitas)} pasta(s).", "ok")
    if falhas:
        flash("Não foi possível fazer a cópia em: " + "; ".join(falhas), "erro")
    return _voltar()
