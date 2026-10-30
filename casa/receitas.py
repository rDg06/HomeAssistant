import sqlite3
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .util import parse_num, sem_acentos

bp = Blueprint("receitas", __name__, url_prefix="/receitas")

TIPOS = ["Base", "Recheio", "Cobertura", "Outro"]
UNIDADES = {"g": "€/kg", "ml": "€/L", "un": "€/un"}


def _custos(db):
    """Custo total de cada receita, com os preços atuais dos ingredientes."""
    return {
        r[0]: r[1]
        for r in db.execute(
            """SELECT ri.receita_id, SUM(ri.quantidade * i.preco_embalagem / i.qtd_embalagem)
               FROM receita_ingredientes ri JOIN ingredientes i ON i.id = ri.ingrediente_id
               GROUP BY ri.receita_id"""
        )
    }


def _ingredientes(db):
    return db.execute("SELECT * FROM ingredientes ORDER BY nome").fetchall()


def _obter(db, id):
    receita = db.execute("SELECT * FROM receitas WHERE id = ?", (id,)).fetchone()
    if receita is None:
        abort(404)
    return receita


@bp.route("/")
def lista():
    db = get_db()
    tipo = request.args.get("tipo", "")
    pesquisa = request.args.get("q", "").strip()
    sql, params = "SELECT * FROM receitas WHERE 1 = 1", []
    if tipo in TIPOS:
        sql += " AND tipo = ?"
        params.append(tipo)
    custos = _custos(db)
    # A pesquisa é feita aqui (e não com LIKE) para ignorar maiúsculas e acentos: "lo" encontra "Pão de Ló".
    procura = sem_acentos(pesquisa)
    receitas = [
        dict(r, custo=custos.get(r["id"], 0))
        for r in db.execute(sql + " ORDER BY tipo, nome", params).fetchall()
        if procura in sem_acentos(r["nome"])
    ]
    return render_template("receitas/lista.html", receitas=receitas, tipos=TIPOS, tipo=tipo, q=pesquisa)


@bp.route("/<int:id>")
def ver(id):
    db = get_db()
    receita = _obter(db, id)
    fator = parse_num(request.args.get("x"), 1)
    if fator <= 0:
        fator = 1
    linhas = db.execute(
        """SELECT ri.quantidade * ? AS quantidade, i.nome, i.unidade,
                  ri.quantidade * ? * i.preco_embalagem / i.qtd_embalagem AS custo
           FROM receita_ingredientes ri JOIN ingredientes i ON i.id = ri.ingrediente_id
           WHERE ri.receita_id = ? ORDER BY ri.id""",
        (fator, fator, id),
    ).fetchall()
    total = sum(l["custo"] for l in linhas)
    return render_template("receitas/ver.html", receita=receita, linhas=linhas, total=total, fator=fator)


def _guardar(receita_id=None):
    f = request.form
    nome = f.get("nome", "").strip()
    if not nome:
        flash("A receita precisa de um nome.", "erro")
        return None
    dados = {
        "nome": nome,
        "tipo": f.get("tipo") if f.get("tipo") in TIPOS else "Outro",
        "porcoes": max(1, f.get("porcoes", type=int) or 1),
        "tamanho": f.get("tamanho", "").strip(),
        "preparo": f.get("preparo", "").strip(),
        "notas": f.get("notas", "").strip(),
    }
    db = get_db()
    # Ignora linhas vazias e ingredientes que entretanto tenham sido apagados.
    validos = {r[0] for r in db.execute("SELECT id FROM ingredientes")}
    linhas = []
    for ingrediente, quantidade in zip(f.getlist("ingrediente_id"), f.getlist("quantidade")):
        q = parse_num(quantidade)
        if ingrediente.isdigit() and int(ingrediente) in validos and q > 0:
            linhas.append((int(ingrediente), q))

    if receita_id is None:
        receita_id = db.execute(
            """INSERT INTO receitas (nome, tipo, porcoes, tamanho, preparo, notas)
               VALUES (:nome, :tipo, :porcoes, :tamanho, :preparo, :notas)""",
            dados,
        ).lastrowid
    else:
        dados["id"] = receita_id
        db.execute(
            """UPDATE receitas SET nome = :nome, tipo = :tipo, porcoes = :porcoes, tamanho = :tamanho,
               preparo = :preparo, notas = :notas WHERE id = :id""",
            dados,
        )
        db.execute("DELETE FROM receita_ingredientes WHERE receita_id = ?", (receita_id,))
    db.executemany(
        "INSERT INTO receita_ingredientes (receita_id, ingrediente_id, quantidade) VALUES (?, ?, ?)",
        [(receita_id, ing, q) for ing, q in linhas],
    )
    db.commit()
    flash(f"Receita \"{nome}\" guardada.", "ok")
    return receita_id


def _form(receita, linhas):
    db = get_db()
    ingredientes = _ingredientes(db)
    ing_js = {
        i["id"]: {"unidade": i["unidade"], "preco": i["preco_embalagem"] / i["qtd_embalagem"]}
        for i in ingredientes
    }
    return render_template(
        "receitas/form.html", receita=receita, linhas=linhas, ingredientes=ingredientes, ing_js=ing_js, tipos=TIPOS
    )


@bp.route("/nova", methods=["GET", "POST"])
def nova():
    if request.method == "POST":
        receita_id = _guardar()
        if receita_id:
            return redirect(url_for(".ver", id=receita_id))
    return _form(None, [])


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    db = get_db()
    receita = _obter(db, id)
    if request.method == "POST" and _guardar(id):
        return redirect(url_for(".ver", id=id))
    linhas = db.execute(
        "SELECT ingrediente_id, quantidade FROM receita_ingredientes WHERE receita_id = ? ORDER BY id", (id,)
    ).fetchall()
    return _form(receita, linhas)


@bp.post("/<int:id>/duplicar")
def duplicar(id):
    db = get_db()
    _obter(db, id)
    novo_id = db.execute(
        """INSERT INTO receitas (nome, tipo, porcoes, tamanho, preparo, notas)
           SELECT nome || ' (cópia)', tipo, porcoes, tamanho, preparo, notas FROM receitas WHERE id = ?""",
        (id,),
    ).lastrowid
    db.execute(
        """INSERT INTO receita_ingredientes (receita_id, ingrediente_id, quantidade)
           SELECT ?, ingrediente_id, quantidade FROM receita_ingredientes WHERE receita_id = ? ORDER BY id""",
        (novo_id, id),
    )
    db.commit()
    flash("Receita duplicada. Ajusta o que for diferente.", "ok")
    return redirect(url_for(".editar", id=novo_id))


@bp.post("/<int:id>/apagar")
def apagar(id):
    db = get_db()
    db.execute("DELETE FROM receitas WHERE id = ?", (id,))
    db.commit()
    flash("Receita apagada.", "ok")
    return redirect(url_for(".lista"))


@bp.route("/ingredientes", methods=["GET", "POST"])
def ingredientes():
    db = get_db()
    if request.method == "POST":
        f = request.form
        nome = f.get("nome", "").strip()
        unidade = f.get("unidade") if f.get("unidade") in UNIDADES else "g"
        qtd = parse_num(f.get("qtd_embalagem"), None)
        preco = parse_num(f.get("preco_embalagem"), None)
        ingrediente_id = f.get("id", type=int)
        if not nome or not qtd or qtd <= 0 or preco is None or preco < 0:
            flash("Indica o nome, a quantidade da embalagem e o preço.", "erro")
            return redirect(url_for(".ingredientes"))
        try:
            if ingrediente_id:
                alterados = db.execute(
                    """UPDATE ingredientes SET nome = ?, unidade = ?, qtd_embalagem = ?, preco_embalagem = ?,
                       atualizado_em = ? WHERE id = ?""",
                    (nome, unidade, qtd, preco, date.today().isoformat(), ingrediente_id),
                ).rowcount
                if alterados:
                    flash(f"\"{nome}\" atualizado. As receitas que o usam já têm o novo custo.", "ok")
                else:
                    flash("Esse ingrediente já não existe (foi apagado entretanto).", "erro")
            else:
                db.execute(
                    """INSERT INTO ingredientes (nome, unidade, qtd_embalagem, preco_embalagem, atualizado_em)
                       VALUES (?, ?, ?, ?, ?)""",
                    (nome, unidade, qtd, preco, date.today().isoformat()),
                )
                flash(f"\"{nome}\" adicionado.", "ok")
            db.commit()
        except sqlite3.IntegrityError:
            flash("Já existe um ingrediente com esse nome.", "erro")
        return redirect(url_for(".ingredientes"))

    lista_ing = db.execute(
        """SELECT i.*, i.preco_embalagem / i.qtd_embalagem AS preco_unit, COUNT(DISTINCT ri.receita_id) AS n_receitas
           FROM ingredientes i LEFT JOIN receita_ingredientes ri ON ri.ingrediente_id = i.id
           GROUP BY i.id ORDER BY i.nome"""
    ).fetchall()
    return render_template("receitas/ingredientes.html", ingredientes=lista_ing, unidades=UNIDADES)


@bp.post("/ingredientes/<int:id>/apagar")
def apagar_ingrediente(id):
    db = get_db()
    usado_em = [
        r[0]
        for r in db.execute(
            """SELECT DISTINCT r.nome FROM receita_ingredientes ri JOIN receitas r ON r.id = ri.receita_id
               WHERE ri.ingrediente_id = ?""",
            (id,),
        )
    ]
    if usado_em:
        flash("Não dá para apagar: é usado em " + ", ".join(usado_em) + ".", "erro")
    else:
        db.execute("DELETE FROM ingredientes WHERE id = ?", (id,))
        db.commit()
        flash("Ingrediente apagado.", "ok")
    return redirect(url_for(".ingredientes"))
