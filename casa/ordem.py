"""Ordem das listas de configuração (categorias, filamentos, ingredientes e extras dos bolos).

Por defeito ficam por ordem alfabética (sem distinguir maiúsculas nem acentos). Ao arrastar uma linha, a lista
passa a ter a ordem escolhida (coluna `ordem`, a começar em 1); "Repor A–Z" volta à ordem alfabética.
Numa lista com ordem própria, o que se acrescentar depois fica no fim.
"""
from flask import Blueprint, abort, redirect, request

from .db import get_db

bp = Blueprint("ordem", __name__, url_prefix="/ordem")

# Listas que se podem reordenar (o nome vem do URL, por isso só estas são aceites).
TABELAS = ("categorias", "filamentos", "ingredientes", "extras_bolo")


def ordenar(alias=""):
    """O ORDER BY das listas: primeiro a ordem escolhida, senão a alfabética."""
    p = f"{alias}." if alias else ""
    return f"{p}ordem IS NULL, {p}ordem, {p}nome COLLATE PT"


def proxima(db, tabela):
    """A `ordem` de um registo novo: no fim, se a lista tiver ordem própria; senão nenhuma (fica no sítio alfabético)."""
    assert tabela in TABELAS
    return db.execute(f"SELECT MAX(ordem) + 1 FROM {tabela}").fetchone()[0]


def _tabela(tabela):
    if tabela not in TABELAS:
        abort(404)
    return tabela


def _voltar():
    destino = request.form.get("voltar", "")
    # Só caminhos desta app (nunca "//outro-site" nem "https://...").
    return redirect(destino if destino.startswith("/") and not destino.startswith("//") else "/")


@bp.post("/<tabela>")
def guardar(tabela):
    """Recebe a lista dos ids pela ordem nova (JSON). Os que faltarem vão para o fim, por ordem alfabética."""
    tabela = _tabela(tabela)
    ids = request.get_json(silent=True)
    if not isinstance(ids, list):
        abort(400)
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError, OverflowError):
        abort(400)
    db = get_db()
    existentes = [r[0] for r in db.execute(f"SELECT id FROM {tabela} ORDER BY {ordenar()}")]
    vistos = set()
    nova = [i for i in ids if i in set(existentes) and not (i in vistos or vistos.add(i))]
    nova += [i for i in existentes if i not in vistos]
    db.executemany(f"UPDATE {tabela} SET ordem = ? WHERE id = ?", [(n, i) for n, i in enumerate(nova, 1)])
    db.commit()
    return {"ok": True}


@bp.post("/<tabela>/repor")
def repor(tabela):
    db = get_db()
    db.execute(f"UPDATE {_tabela(tabela)} SET ordem = NULL")
    db.commit()
    return _voltar()
