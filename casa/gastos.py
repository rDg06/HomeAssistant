import calendar
import math
import sqlite3
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .util import data_valida, deslocar_mes, existe, hoje_mes, mes_valido, nome_mes, parse_num

bp = Blueprint("gastos", __name__, url_prefix="/gastos")


TIPOS_RENDIMENTO = ["Salário", "Cartão refeição", "Extra"]  # ordem no resumo do mês
PESSOAS = ["Rodrigo", "Carina"]  # por esta ordem na janela
PRIMEIRO_MES = "2026-11"  # os gastos começam a ser registados neste mês


def mes_atual():
    """Mês a mostrar por defeito: o de hoje, mas nunca antes do primeiro mês."""
    return max(hoje_mes(), PRIMEIRO_MES)


def _mes_pedido(mes):
    return mes if mes_valido(mes) and mes >= PRIMEIRO_MES else mes_atual()


def total_mes(db, mes, tabela="gastos"):
    return db.execute(
        f"SELECT COALESCE(SUM(valor), 0) FROM {tabela} WHERE substr(data, 1, 7) = ?", (mes,)
    ).fetchone()[0]


# Valores pedidos por pessoa na janela "Rendimentos do mês": (campo do formulário, tipo, repete-se todos os meses).
CAMPOS_JANELA = [("salario", "Salário", True), ("cartao", "Cartão refeição", True), ("extra", "Extra", False)]


def _janela_rendimentos(db, mes):
    """Valores para preencher a janela: os deste mês ou, se ainda não houver, os mais recentes.

    O extra não se repete, por isso só aparece se já tiver sido posto neste mês.
    """
    blocos, do_mes_anterior = [], False
    for pessoa in PESSOAS:
        valores = {}
        for campo, tipo, mensal in CAMPOS_JANELA:
            linha = db.execute(
                f"""SELECT valor, substr(data, 1, 7) = ? AS deste_mes FROM rendimentos
                    WHERE pessoa = ? AND tipo = ? AND substr(data, 1, 7) {'<=' if mensal else '='} ?
                    ORDER BY data DESC, id DESC LIMIT 1""",
                (mes, pessoa, tipo, mes),
            ).fetchone()
            valores[campo] = linha["valor"] if linha else None
            do_mes_anterior |= bool(linha and not linha["deste_mes"])
        blocos.append({"pessoa": pessoa, **valores})
    return {"blocos": blocos, "do_mes_anterior": do_mes_anterior}


def _fixas_por_lancar(db, mes):
    """Despesas fixas ativas que ainda não têm gasto lançado neste mês."""
    return db.execute(
        """SELECT * FROM despesas_fixas f
           WHERE f.ativa = 1 AND NOT EXISTS (
               SELECT 1 FROM gastos g WHERE g.fixa_id = f.id AND substr(g.data, 1, 7) = ?
           ) ORDER BY f.dia, f.descricao""",
        (mes,),
    ).fetchall()


def _categorias(db):
    return db.execute("SELECT * FROM categorias ORDER BY nome").fetchall()


def _ler_form():
    f = request.form
    dados = {
        "data": data_valida(f.get("data")),
        "descricao": f.get("descricao", "").strip(),
        "categoria_id": existe(get_db(), "categorias", f.get("categoria_id", type=int)),
        "valor": parse_num(f.get("valor"), None),
        "notas": f.get("notas", "").strip(),
    }
    erros = []
    if not dados["data"]:
        erros.append("Data inválida.")
    elif dados["data"][:7] < PRIMEIRO_MES:
        erros.append("Os gastos começam em Novembro de 2026.")
    if not dados["descricao"]:
        erros.append("Falta a descrição.")
    if dados["valor"] is None or dados["valor"] <= 0:
        erros.append("O valor tem de ser maior que zero.")
    return dados, erros


CORES = 8  # cores distintas no gráfico; ver .serie-N em style.css
RAIO = 70
PERIMETRO = 2 * math.pi * RAIO
ESPACO = 2  # separação entre fatias


def _fatias(db, por_categoria, total):
    """Fatias do gráfico circular, da maior para a menor.

    Cada categoria tem sempre a mesma cor (pela ordem em que foi criada), para não mudar de cor de mês
    para mês. "Sem categoria" e categorias além da 8.ª ficam a cinzento.
    """
    ordem = {r[0]: i for i, r in enumerate(db.execute("SELECT id FROM categorias ORDER BY id"))}
    fatias, inicio = [], 0.0
    for c in por_categoria:
        posicao = ordem.get(c["id"])
        comprimento = c["total"] / total * PERIMETRO if total else 0
        visivel = comprimento if len(por_categoria) == 1 else max(comprimento - ESPACO, 0.5)
        fatias.append({
            "nome": c["nome"],
            "total": c["total"],
            "pct": c["total"] / total * 100 if total else 0,
            "serie": posicao + 1 if posicao is not None and posicao < CORES else 0,
            "traco": f"{visivel:.2f} {PERIMETRO:.2f}",
            "desvio": f"{-inicio:.2f}",
        })
        inicio += comprimento
    return fatias


@bp.route("/")
def lista():
    mes = _mes_pedido(request.args.get("mes", ""))
    db = get_db()

    gastos = db.execute(
        """SELECT g.*, c.nome AS categoria FROM gastos g
           LEFT JOIN categorias c ON c.id = g.categoria_id
           WHERE substr(g.data, 1, 7) = ? ORDER BY g.data DESC, g.id DESC""",
        (mes,),
    ).fetchall()
    por_categoria = db.execute(
        """SELECT c.id, COALESCE(c.nome, 'Sem categoria') AS nome, SUM(g.valor) AS total FROM gastos g
           LEFT JOIN categorias c ON c.id = g.categoria_id
           WHERE substr(g.data, 1, 7) = ? GROUP BY c.id ORDER BY total DESC""",
        (mes,),
    ).fetchall()
    total = total_mes(db, mes)
    por_tipo = dict(db.execute(
        "SELECT tipo, SUM(valor) FROM rendimentos WHERE substr(data, 1, 7) = ? GROUP BY tipo", (mes,)
    ).fetchall())
    total_rendimentos = sum(por_tipo.values())

    anterior = deslocar_mes(mes, -1)
    if anterior < PRIMEIRO_MES:
        anterior = None
    historico = [
        (m, total_mes(db, m)) for m in (deslocar_mes(mes, -i) for i in range(5, -1, -1)) if m >= PRIMEIRO_MES
    ]
    por_lancar = _fixas_por_lancar(db, mes)

    return render_template(
        "gastos/lista.html",
        mes=mes,
        anterior=anterior,
        seguinte=deslocar_mes(mes, 1),
        gastos=gastos,
        fatias=_fatias(db, por_categoria, total),
        total=total,
        por_tipo=sorted(por_tipo.items(), key=lambda par: TIPOS_RENDIMENTO.index(par[0]) if par[0] in TIPOS_RENDIMENTO else 99),
        total_rendimentos=total_rendimentos,
        janela=_janela_rendimentos(db, mes),
        total_anterior=total_mes(db, anterior) if anterior else 0,
        primeiro_mes=PRIMEIRO_MES,
        historico=historico,
        max_hist=max(t for _, t in historico),
        por_lancar=por_lancar,
        total_por_lancar=sum(f["valor"] for f in por_lancar),
        categorias=_categorias(db),
        data_padrao=date.today().isoformat() if mes == hoje_mes() else f"{mes}-01",
    )


@bp.post("/novo")
def novo():
    dados, erros = _ler_form()
    if erros:
        for erro in erros:
            flash(erro, "erro")
        return redirect(url_for(".lista", mes=request.form.get("mes")))
    db = get_db()
    db.execute(
        """INSERT INTO gastos (data, descricao, categoria_id, valor, notas)
           VALUES (:data, :descricao, :categoria_id, :valor, :notas)""",
        dados,
    )
    db.commit()
    flash("Gasto registado.", "ok")
    return redirect(url_for(".lista", mes=dados["data"][:7]))


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    db = get_db()
    gasto = db.execute("SELECT * FROM gastos WHERE id = ?", (id,)).fetchone()
    if gasto is None:
        abort(404)
    if request.method == "POST":
        dados, erros = _ler_form()
        if not erros:
            dados["id"] = id
            db.execute(
                """UPDATE gastos SET data = :data, descricao = :descricao, categoria_id = :categoria_id,
                   valor = :valor, notas = :notas WHERE id = :id""",
                dados,
            )
            db.commit()
            flash("Gasto atualizado.", "ok")
            return redirect(url_for(".lista", mes=dados["data"][:7]))
        for erro in erros:
            flash(erro, "erro")
        # Mantém o que foi escrito nos campos válidos para não se perder.
        gasto = {**dict(gasto), **{k: v for k, v in dados.items() if v not in (None, "")}}
    return render_template("gastos/editar.html", gasto=gasto, categorias=_categorias(db), primeiro_mes=PRIMEIRO_MES)


@bp.post("/<int:id>/apagar")
def apagar(id):
    db = get_db()
    gasto = db.execute("SELECT data FROM gastos WHERE id = ?", (id,)).fetchone()
    db.execute("DELETE FROM gastos WHERE id = ?", (id,))
    db.commit()
    flash("Gasto apagado.", "ok")
    return redirect(url_for(".lista", mes=gasto["data"][:7] if gasto else None))


@bp.post("/fixas/lancar")
def lancar_fixas():
    """Lança no mês as despesas fixas ativas que ainda lá não estão."""
    mes = request.form.get("mes", "")
    if not mes_valido(mes) or mes < PRIMEIRO_MES:
        abort(400)
    db = get_db()
    ano, m = map(int, mes.split("-"))
    ultimo_dia = calendar.monthrange(ano, m)[1]
    por_lancar = _fixas_por_lancar(db, mes)
    for fixa in por_lancar:
        dia = min(max(fixa["dia"], 1), ultimo_dia)  # dia 31 em Fevereiro fica no último dia
        db.execute(
            """INSERT INTO gastos (data, descricao, categoria_id, valor, fixo, fixa_id, notas)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (f"{mes}-{dia:02d}", fixa["descricao"], fixa["categoria_id"], fixa["valor"], fixa["id"], fixa["notas"]),
        )
    db.commit()
    if por_lancar:
        flash(f"Lançadas {len(por_lancar)} despesa(s) fixa(s) em {nome_mes(mes)}.", "ok")
    else:
        flash("As despesas fixas já estavam todas lançadas neste mês.", "ok")
    return redirect(url_for(".lista", mes=mes))


@bp.route("/fixas", methods=["GET", "POST"])
def fixas():
    db = get_db()
    if request.method == "POST":
        f = request.form
        dados = {
            "descricao": f.get("descricao", "").strip(),
            "categoria_id": existe(db, "categorias", f.get("categoria_id", type=int)),
            "valor": parse_num(f.get("valor"), None),
            "dia": min(max(f.get("dia", type=int) or 1, 1), 31),
            "ativa": 1 if f.get("ativa") else 0,
            "id": f.get("id", type=int),
        }
        if not dados["descricao"] or dados["valor"] is None or dados["valor"] <= 0:
            flash("Indica o nome e um valor maior que zero.", "erro")
        elif dados["id"]:
            alterados = db.execute(
                """UPDATE despesas_fixas SET descricao = :descricao, categoria_id = :categoria_id, valor = :valor,
                   dia = :dia, ativa = :ativa WHERE id = :id""",
                dados,
            ).rowcount
            db.commit()
            if alterados:
                flash(f"\"{dados['descricao']}\" atualizada. Vale para os meses que ainda não foram lançados.", "ok")
            else:
                flash("Essa despesa fixa já não existe (foi apagada entretanto).", "erro")
        else:
            db.execute(
                """INSERT INTO despesas_fixas (descricao, categoria_id, valor, dia, ativa)
                   VALUES (:descricao, :categoria_id, :valor, :dia, 1)""",
                dados,
            )
            db.commit()
            flash(f"\"{dados['descricao']}\" adicionada às despesas fixas.", "ok")
        return redirect(url_for(".fixas"))

    lista_fixas = db.execute(
        """SELECT f.*, c.nome AS categoria FROM despesas_fixas f
           LEFT JOIN categorias c ON c.id = f.categoria_id
           ORDER BY f.ativa DESC, f.dia, f.descricao"""
    ).fetchall()
    return render_template(
        "gastos/fixas.html",
        fixas=lista_fixas,
        total=sum(f["valor"] for f in lista_fixas if f["ativa"]),
        categorias=_categorias(db),
    )


@bp.post("/fixas/<int:id>/apagar")
def apagar_fixa(id):
    db = get_db()
    db.execute("DELETE FROM despesas_fixas WHERE id = ?", (id,))
    db.commit()
    flash("Despesa fixa apagada. Os gastos já lançados nos meses anteriores mantêm-se.", "ok")
    return redirect(url_for(".fixas"))


@bp.post("/rendimentos/mes")
def rendimentos_mes():
    """Grava de uma vez o salário e o cartão refeição de cada pessoa (janela "Rendimentos do mês").

    Atualiza o valor se já existir neste mês, cria-o se não existir e apaga-o se o campo ficar vazio.
    """
    f = request.form
    mes = f.get("mes", "")
    if not mes_valido(mes) or mes < PRIMEIRO_MES:
        abort(400)
    db = get_db()
    data_nova = date.today().isoformat() if mes == hoje_mes() else f"{mes}-01"
    alterados = 0
    for i, pessoa in enumerate(PESSOAS, start=1):
        for campo, tipo, mensal in CAMPOS_JANELA:
            valor = parse_num(f.get(f"{campo}_{i}"), None)
            existente = db.execute(
                "SELECT id FROM rendimentos WHERE substr(data, 1, 7) = ? AND pessoa = ? AND tipo = ? ORDER BY id",
                (mes, pessoa, tipo),
            ).fetchone()
            if valor is None or valor <= 0:
                if existente:
                    db.execute("DELETE FROM rendimentos WHERE id = ?", (existente["id"],))
                    alterados += 1
            elif existente:
                db.execute("UPDATE rendimentos SET valor = ? WHERE id = ?", (valor, existente["id"]))
                alterados += 1
            else:
                db.execute(
                    "INSERT INTO rendimentos (data, pessoa, tipo, valor, fixo) VALUES (?, ?, ?, ?, ?)",
                    (data_nova, pessoa, tipo, valor, int(mensal)),
                )
                alterados += 1
    db.commit()
    flash("Rendimentos do mês guardados." if alterados else "Não havia valores para guardar.", "ok")
    return redirect(url_for(".lista", mes=mes))


@bp.route("/categorias", methods=["GET", "POST"])
def categorias():
    db = get_db()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        categoria_id = request.form.get("id", type=int)
        if not nome:
            flash("A categoria precisa de um nome.", "erro")
            return redirect(url_for(".categorias"))
        try:
            if categoria_id:
                # Os gastos guardam o id da categoria, por isso o nome novo aparece logo em todos os meses.
                alterados = db.execute("UPDATE categorias SET nome = ? WHERE id = ?", (nome, categoria_id)).rowcount
                if alterados:
                    flash(f"Categoria renomeada para \"{nome}\".", "ok")
                else:
                    flash("Essa categoria já não existe (foi apagada entretanto).", "erro")
            else:
                db.execute("INSERT INTO categorias (nome) VALUES (?)", (nome,))
                flash(f"Categoria \"{nome}\" criada.", "ok")
            db.commit()
        except sqlite3.IntegrityError:
            flash(f"Já existe uma categoria chamada \"{nome}\".", "erro")
        return redirect(url_for(".categorias"))
    lista_categorias = db.execute(
        """SELECT c.*, COUNT(g.id) AS n, COALESCE(SUM(g.valor), 0) AS total FROM categorias c
           LEFT JOIN gastos g ON g.categoria_id = c.id GROUP BY c.id ORDER BY c.nome"""
    ).fetchall()
    return render_template("gastos/categorias.html", categorias=lista_categorias)


@bp.post("/categorias/<int:id>/apagar")
def apagar_categoria(id):
    db = get_db()
    db.execute("DELETE FROM categorias WHERE id = ?", (id,))
    db.commit()
    flash("Categoria apagada. Os gastos dessa categoria ficaram sem categoria.", "ok")
    return redirect(url_for(".categorias"))
