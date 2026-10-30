import math
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .util import data_valida, existe, hoje_mes, mes_valido, parse_num

bp = Blueprint("impressao", __name__, url_prefix="/impressao")

# (chave, rótulo, unidade, ajuda)
CONFIG_CAMPOS = [
    ("potencia_w", "Potência média", "W",
     "Consumo médio da A1 a imprimir, não o máximo (1300 W é só em picos de aquecimento). "
     "Com PLA ronda os 100 W; mede com um wattímetro para teres o teu valor."),
    ("preco_kwh", "Preço da eletricidade", "€/kWh", "Preço do kWh na tua fatura de eletricidade."),
    ("valor_hora_trabalho", "Mão de obra", "€/h", "Quanto vale a tua hora de trabalho manual (preparação e acabamentos)."),
    ("prep_min", "Preparação por impressão", "min",
     "Tempo fixo por impressão: preparar no Bambu Studio, arrancar e limpar a chapa. "
     "A A1 calibra-se sozinha, por isso costuma ser curto."),
    ("custo_impressora", "Preço da impressora", "€", "Quanto pagaste pela A1 com o combo AMS lite."),
    ("vida_util_horas", "Vida útil da impressora", "h",
     "Horas de impressão até substituíres a A1. 5000 h é uma estimativa prudente (cerca de 3 anos a 5 h por dia)."),
    ("manutencao_hora", "Manutenção e peças", "€/h",
     "Custo por hora de bico, chapa PEI, hotend e correias. O bico da A1 é de troca rápida e barato."),
    ("taxa_falha_pct", "Falhas e desperdício", "%",
     "Reserva para impressões falhadas e desperdício. Normalmente 5 a 15%. "
     "Com o AMS lite, a purga nas trocas de cor pode pesar bastante."),
    ("margem_pct", "Margem de lucro", "%", "Lucro somado ao custo de produção. Normalmente 20 a 100%."),
]


def ler_config(db):
    return {r["chave"]: r["valor"] for r in db.execute("SELECT chave, valor FROM config")}


def calcular(cfg, preco_kg, gramas, horas, horas_trabalho, extra):
    """Custo de uma unidade. Mesma fórmula que o JavaScript da calculadora.

    A margem aplica-se ao custo de produção; os extras (envio, embalagem) somam-se depois, sem margem.
    `horas_trabalho` é o pós-processamento; a preparação fixa por impressão vem da configuração.
    """
    material = gramas / 1000 * preco_kg
    energia = cfg["potencia_w"] / 1000 * horas * cfg["preco_kwh"]
    vida = max(1, cfg["vida_util_horas"])
    desgaste = (cfg["custo_impressora"] / vida + cfg["manutencao_hora"]) * horas
    mao_obra = (cfg["prep_min"] / 60 + horas_trabalho) * cfg["valor_hora_trabalho"]
    base = material + energia + desgaste + mao_obra
    falhas = base * cfg["taxa_falha_pct"] / 100
    producao = base + falhas
    margem = producao * cfg["margem_pct"] / 100
    return {
        "material": material,
        "energia": energia,
        "desgaste": desgaste,
        "mao_obra": mao_obra,
        "falhas": falhas,
        "producao": producao,
        "margem": margem,
        "extra": extra,
        "total": producao + extra,
        "preco_sugerido": producao + margem + extra,
    }


def pecas_com_custo(db, peca_id=None):
    cfg = ler_config(db)
    sql = """SELECT p.*, f.nome AS filamento, COALESCE(f.preco_kg, 0) AS preco_kg FROM pecas p
             LEFT JOIN filamentos f ON f.id = p.filamento_id"""
    if peca_id is not None:
        rows = db.execute(sql + " WHERE p.id = ?", (peca_id,)).fetchall()
    else:
        rows = db.execute(sql + " ORDER BY p.nome").fetchall()
    pecas = []
    for r in rows:
        custo = calcular(cfg, r["preco_kg"], r["gramas"], r["horas"], r["horas_trabalho"], r["custos_extra"])
        preco = r["preco_venda"] if r["preco_venda"] is not None else custo["preco_sugerido"]
        pecas.append(dict(r, custo=custo, preco=preco, lucro=preco - custo["total"]))
    return pecas


def resumo_vendas(db, prefixo):
    """Totais das vendas cuja data começa por `prefixo` ("2026" ou "2026-10")."""
    r = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(quantidade), 0) AS unidades,
                  COALESCE(SUM(quantidade * preco_unit), 0) AS faturado,
                  COALESCE(SUM(quantidade * custo_unit + outros_custos), 0) AS custos
           FROM vendas WHERE data LIKE ?""",
        (prefixo + "%",),
    ).fetchone()
    return dict(r, lucro=r["faturado"] - r["custos"])


def _filamentos(db):
    return db.execute("SELECT * FROM filamentos ORDER BY material, nome").fetchall()


@bp.route("/")
def painel():
    db = get_db()
    mes = hoje_mes()
    ultimas = db.execute(
        """SELECT *, quantidade * (preco_unit - custo_unit) - outros_custos AS lucro
           FROM vendas ORDER BY data DESC, id DESC LIMIT 5"""
    ).fetchall()
    return render_template(
        "impressao/painel.html",
        mes=mes,
        resumo_mes=resumo_vendas(db, mes),
        resumo_ano=resumo_vendas(db, mes[:4]),
        pecas=pecas_com_custo(db),
        ultimas=ultimas,
    )


@bp.route("/calculadora", methods=["GET", "POST"])
def calculadora():
    db = get_db()
    if request.method == "POST":
        f = request.form
        positivo = lambda campo: max(0.0, parse_num(f.get(campo)))
        preco_venda = parse_num(f.get("preco_venda"), None)
        dados = {
            "nome": f.get("nome", "").strip() or "Peça sem nome",
            "filamento_id": existe(db, "filamentos", f.get("filamento_id", type=int)),
            "gramas": positivo("gramas"),
            "horas": positivo("horas_h") + positivo("horas_m") / 60,
            "horas_trabalho": positivo("trabalho_min") / 60,
            "custos_extra": positivo("custos_extra"),
            "preco_venda": max(0.0, preco_venda) if preco_venda is not None else None,
            "notas": f.get("notas", "").strip(),
        }
        peca_id = f.get("id", type=int)
        if peca_id:
            dados["id"] = peca_id
            db.execute(
                """UPDATE pecas SET nome = :nome, filamento_id = :filamento_id, gramas = :gramas,
                   horas = :horas, horas_trabalho = :horas_trabalho, custos_extra = :custos_extra,
                   preco_venda = :preco_venda, notas = :notas WHERE id = :id""",
                dados,
            )
            flash(f"Peça \"{dados['nome']}\" atualizada.", "ok")
        else:
            db.execute(
                """INSERT INTO pecas (nome, filamento_id, gramas, horas, horas_trabalho, custos_extra, preco_venda, notas)
                   VALUES (:nome, :filamento_id, :gramas, :horas, :horas_trabalho, :custos_extra, :preco_venda, :notas)""",
                dados,
            )
            flash(f"Peça \"{dados['nome']}\" guardada.", "ok")
        db.commit()
        return redirect(url_for(".painel"))

    peca = None
    peca_id = request.args.get("id", type=int)
    if peca_id:
        peca = db.execute("SELECT * FROM pecas WHERE id = ?", (peca_id,)).fetchone()
        if peca is None:
            abort(404)
    return render_template(
        "impressao/calculadora.html", peca=peca, filamentos=_filamentos(db), cfg=ler_config(db)
    )


@bp.post("/pecas/<int:id>/apagar")
def apagar_peca(id):
    db = get_db()
    db.execute("DELETE FROM pecas WHERE id = ?", (id,))
    db.commit()
    flash("Peça apagada. As vendas já registadas mantêm-se.", "ok")
    return redirect(url_for(".painel"))


@bp.route("/vendas")
def vendas():
    mes = request.args.get("mes", "")
    if not mes_valido(mes):
        mes = hoje_mes()
    db = get_db()
    lista = db.execute(
        """SELECT *, quantidade * (preco_unit - custo_unit) - outros_custos AS lucro
           FROM vendas WHERE substr(data, 1, 7) = ? ORDER BY data DESC, id DESC""",
        (mes,),
    ).fetchall()
    return render_template(
        "impressao/vendas.html",
        mes=mes,
        vendas=lista,
        resumo=resumo_vendas(db, mes),
        pecas=pecas_com_custo(db),
        peca_escolhida=request.args.get("peca", type=int),
        data_padrao=date.today().isoformat() if mes == hoje_mes() else f"{mes}-01",
    )


@bp.post("/vendas/nova")
def nova_venda():
    db = get_db()
    f = request.form
    data_venda = data_valida(f.get("data")) or date.today().isoformat()
    peca_id = f.get("peca_id", type=int)
    encontradas = pecas_com_custo(db, peca_id) if peca_id else []
    peca = encontradas[0] if encontradas else None
    if peca is None:
        peca_id = None  # a peça pode ter sido apagada entretanto

    descricao = f.get("descricao", "").strip() or (peca["nome"] if peca else "")
    preco_unit = parse_num(f.get("preco_unit"), None)
    if preco_unit is None and peca:
        preco_unit = round(peca["preco"], 2)
    custo_unit = parse_num(f.get("custo_unit"), None)
    if custo_unit is None:
        custo_unit = round(peca["custo"]["total"], 2) if peca else 0
    custo_unit = max(0.0, custo_unit)

    if not descricao or preco_unit is None or preco_unit < 0:
        flash("Indica o que vendeste e o preço.", "erro")
        return redirect(url_for(".vendas", mes=data_venda[:7]))

    db.execute(
        """INSERT INTO vendas (data, peca_id, descricao, quantidade, preco_unit, custo_unit, outros_custos, cliente, notas)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data_venda,
            peca_id,
            descricao,
            max(1, f.get("quantidade", type=int) or 1),
            preco_unit,
            custo_unit,
            max(0.0, parse_num(f.get("outros_custos"))),
            f.get("cliente", "").strip(),
            f.get("notas", "").strip(),
        ),
    )
    db.commit()
    flash("Venda registada.", "ok")
    return redirect(url_for(".vendas", mes=data_venda[:7]))


@bp.post("/vendas/orcamento")
def registar_orcamento():
    """Regista como vendas os pedidos do orçamento da calculadora (enviados em JSON)."""
    itens = request.get_json(silent=True)
    if not isinstance(itens, list) or not itens:
        abort(400)
    db = get_db()
    hoje = date.today().isoformat()
    for item in itens:
        if not isinstance(item, dict):
            abort(400)
        try:
            linha = (
                hoje,
                str(item.get("nome") or "Impressão 3D")[:200],
                max(1, int(item.get("qtd") or 1)),
                float(item["preco_unit"]),
                float(item.get("custo_unit") or 0),
                str(item.get("cliente") or "")[:200],
            )
        except (KeyError, TypeError, ValueError):
            abort(400)
        if not all(math.isfinite(v) and v >= 0 for v in linha[3:5]):
            abort(400)
        db.execute(
            """INSERT INTO vendas (data, descricao, quantidade, preco_unit, custo_unit, cliente)
               VALUES (?, ?, ?, ?, ?, ?)""",
            linha,
        )
    db.commit()
    flash(f"{len(itens)} pedido(s) registado(s) como venda.", "ok")
    return {"ok": True, "url": url_for(".vendas")}


@bp.post("/vendas/<int:id>/apagar")
def apagar_venda(id):
    db = get_db()
    venda = db.execute("SELECT data FROM vendas WHERE id = ?", (id,)).fetchone()
    db.execute("DELETE FROM vendas WHERE id = ?", (id,))
    db.commit()
    flash("Venda apagada.", "ok")
    return redirect(url_for(".vendas", mes=venda["data"][:7] if venda else None))


def _ir_para_filamentos():
    return redirect(url_for(".configuracao", _anchor="filamentos"))


@bp.route("/filamentos", methods=["GET", "POST"])
def filamentos():
    """Os filamentos são geridos na página de configuração; aqui só se gravam."""
    if request.method == "GET":
        return _ir_para_filamentos()
    db = get_db()
    f = request.form
    nome = f.get("nome", "").strip()
    material = f.get("material", "").strip() or "PLA"
    preco_kg = parse_num(f.get("preco_kg"), None)
    filamento_id = f.get("id", type=int)
    if not nome or preco_kg is None or preco_kg < 0:
        flash("Indica o nome e o preço por kg do filamento.", "erro")
    elif filamento_id:
        alterados = db.execute(
            "UPDATE filamentos SET nome = ?, material = ?, preco_kg = ? WHERE id = ?",
            (nome, material, preco_kg, filamento_id),
        ).rowcount
        db.commit()
        if alterados:
            flash(f"Filamento \"{nome}\" atualizado.", "ok")
        else:
            flash("Esse filamento já não existe (foi apagado entretanto).", "erro")
    else:
        db.execute(
            "INSERT INTO filamentos (nome, material, preco_kg) VALUES (?, ?, ?)", (nome, material, preco_kg)
        )
        db.commit()
        flash(f"Filamento \"{nome}\" adicionado.", "ok")
    return _ir_para_filamentos()


@bp.post("/filamentos/<int:id>/apagar")
def apagar_filamento(id):
    db = get_db()
    db.execute("DELETE FROM filamentos WHERE id = ?", (id,))
    db.commit()
    flash("Filamento apagado.", "ok")
    return _ir_para_filamentos()


@bp.route("/configuracao", methods=["GET", "POST"])
def configuracao():
    db = get_db()
    if request.method == "POST":
        for chave, *_ in CONFIG_CAMPOS:
            valor = parse_num(request.form.get(chave), None)
            minimo = 1 if chave == "vida_util_horas" else 0
            if valor is not None and valor >= minimo:
                db.execute("UPDATE config SET valor = ? WHERE chave = ?", (valor, chave))
        db.commit()
        flash("Configuração guardada. Os custos das peças foram recalculados.", "ok")
        return redirect(url_for(".configuracao"))
    filamentos = db.execute(
        """SELECT f.*, COUNT(p.id) AS n_pecas FROM filamentos f
           LEFT JOIN pecas p ON p.filamento_id = f.id GROUP BY f.id ORDER BY f.material, f.nome"""
    ).fetchall()
    return render_template(
        "impressao/configuracao.html", campos=CONFIG_CAMPOS, cfg=ler_config(db), filamentos=filamentos
    )
