"""Preços dos ingredientes a partir das páginas de produto do Continente.

A página de cada produto traz os dados em JSON-LD (schema.org "Product"): nome e preço atual.
O tamanho da embalagem ("emb. 1 kg") vem no texto da página.
"""
import json
import re
import ssl
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import truststore
from flask import current_app

from .db import get_db
from .util import eur

DIAS_ENTRE_VERIFICACOES = 30
HORAS_ENTRE_RONDAS = 12  # no máximo uma ronda automática a cada 12 h
PAUSA_ENTRE_PEDIDOS = 1.0  # segundos, para não sobrecarregar o site
TAMANHO_MAXIMO = 8 * 1024 * 1024
CABECALHOS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-PT,pt;q=0.9",
}
# Unidade da embalagem no site -> (unidade usada na app, multiplicador)
UNIDADES = {
    "kg": ("g", 1000), "g": ("g", 1), "gr": ("g", 1),
    "l": ("ml", 1000), "lt": ("ml", 1000), "cl": ("ml", 10), "ml": ("ml", 1),
    "un": ("un", 1), "unid": ("un", 1), "uni": ("un", 1),
}


class ErroPreco(Exception):
    """Mensagem para mostrar ao utilizador quando não dá para ler o preço."""


def link_valido(link):
    url = urlparse(link or "")
    host = url.hostname or ""
    # Só o próprio site (e não, por exemplo, "falsocontinente.pt").
    return url.scheme == "https" and (host == "continente.pt" or host.endswith(".continente.pt"))


def _descarregar(link):
    # Usa os certificados do sistema operativo (o Python no Windows nem sempre os encontra sozinho).
    contexto = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    pedido = urllib.request.Request(link, headers=CABECALHOS)
    try:
        with urllib.request.urlopen(pedido, timeout=20, context=contexto) as resposta:
            return resposta.read(TAMANHO_MAXIMO).decode("utf-8", "replace")
    except Exception as erro:
        raise ErroPreco(f"Não foi possível abrir a página do Continente ({erro}).") from erro


def _produto_json_ld(html):
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            dados = json.loads(bloco)
        except ValueError:
            continue
        for item in dados if isinstance(dados, list) else [dados]:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def _embalagem(html):
    """Lê "emb. 1 kg", "emb. 6 x 1 lt", "emb. 12 un"... e devolve (quantidade, unidade) ou (None, None)."""
    m = re.search(r'ct-pdp--unit[^>]*>\s*([^<]+)', html)
    texto = m.group(1).strip().lower() if m else ""
    m = re.search(r'(?:(\d+)\s*x\s*)?(\d+(?:[.,]\d+)?)\s*([a-z]+)', texto)
    if not m or m.group(3) not in UNIDADES:
        return None, None
    unidade, multiplicador = UNIDADES[m.group(3)]
    vezes = int(m.group(1) or 1)
    return round(vezes * float(m.group(2).replace(",", ".")) * multiplicador, 3), unidade


def ler_produto(link):
    """Devolve {nome, preco, quantidade, unidade, disponivel} de uma página de produto do Continente."""
    if not link_valido(link):
        raise ErroPreco("O link tem de ser de uma página de produto do Continente (https://www.continente.pt/...).")
    html = _descarregar(link)
    produto = _produto_json_ld(html)
    if not produto:
        raise ErroPreco("A página não tem os dados do produto (o site pode ter mudado ou o link não é de um produto).")
    ofertas = produto.get("offers") or {}
    if isinstance(ofertas, list):
        ofertas = ofertas[0] if ofertas else {}
    try:
        preco = float(str(ofertas.get("price")).replace(",", "."))
    except (TypeError, ValueError):
        raise ErroPreco("Não encontrei o preço na página.") from None
    if not 0 < preco < 10000:
        raise ErroPreco("O preço lido não parece válido.")
    quantidade, unidade = _embalagem(html)
    return {
        "nome": (produto.get("name") or "").strip(),
        "preco": preco,
        "quantidade": quantidade,
        "unidade": unidade,
        "disponivel": "InStock" in str(ofertas.get("availability", "")),
    }


def atualizar_ingrediente(db, ingrediente):
    """Vai ver o preço de um ingrediente com link. Devolve (resultado, mensagem), com resultado
    "mudou", "igual" ou "aviso"."""
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        produto = ler_produto(ingrediente["link"])
    except ErroPreco as erro:
        db.execute("UPDATE ingredientes SET verificado_em = ?, aviso_preco = ? WHERE id = ?",
                   (agora, str(erro), ingrediente["id"]))
        db.commit()
        return "aviso", f"{ingrediente['nome']}: {erro}"

    # Se a embalagem mudou de tamanho, o preço por g/ml já não é comparável: não muda nada e avisa.
    if produto["quantidade"] and (produto["unidade"], produto["quantidade"]) != (
        ingrediente["unidade"], ingrediente["qtd_embalagem"]
    ):
        aviso = (f"No site a embalagem é de {produto['quantidade']:g} {produto['unidade']} "
                 f"(aqui está {ingrediente['qtd_embalagem']:g} {ingrediente['unidade']}). Confirma e corrige.")
        db.execute("UPDATE ingredientes SET verificado_em = ?, aviso_preco = ? WHERE id = ?",
                   (agora, aviso, ingrediente["id"]))
        db.commit()
        return "aviso", f"{ingrediente['nome']}: {aviso}"

    aviso = "" if produto["disponivel"] else "Esgotado no site (o preço pode não estar atualizado)."
    if produto["preco"] != ingrediente["preco_embalagem"]:
        db.execute("INSERT INTO precos_historico (ingrediente_id, data, preco) VALUES (?, ?, ?)",
                   (ingrediente["id"], date.today().isoformat(), produto["preco"]))
    db.execute(
        """UPDATE ingredientes SET preco_embalagem = ?, atualizado_em = ?, verificado_em = ?, aviso_preco = ?
           WHERE id = ?""",
        (produto["preco"], date.today().isoformat(), agora, aviso, ingrediente["id"]),
    )
    db.commit()
    if produto["preco"] != ingrediente["preco_embalagem"]:
        return "mudou", f"{ingrediente['nome']}: {eur(ingrediente['preco_embalagem'])} → {eur(produto['preco'])}"
    return ("aviso" if aviso else "igual"), f"{ingrediente['nome']}: sem alteração ({eur(produto['preco'])})"


def atualizar_todos(db, so_desatualizados=True):
    """Atualiza os ingredientes com link (por defeito, só os verificados há mais de 30 dias).
    Devolve a lista de (resultado, mensagem) de atualizar_ingrediente."""
    limite = (datetime.now() - timedelta(days=DIAS_ENTRE_VERIFICACOES)).isoformat(timespec="seconds")
    sql = "SELECT * FROM ingredientes WHERE link != ''"
    if so_desatualizados:
        sql += " AND (verificado_em IS NULL OR verificado_em < ?)"
    ingredientes = db.execute(sql + " ORDER BY nome", (limite,) if so_desatualizados else ()).fetchall()
    mensagens = []
    for i, ingrediente in enumerate(ingredientes):
        if i:
            time.sleep(PAUSA_ENTRE_PEDIDOS)
        mensagens.append(atualizar_ingrediente(db, ingrediente))
    return mensagens


def verificar_em_segundo_plano():
    """Chamado ao abrir as Receitas: se já passaram 12 h desde a última ronda, atualiza em segundo plano.

    A data da última ronda fica na base de dados, para funcionar mesmo que a app seja reiniciada.
    """
    if current_app.config.get("TESTING"):
        return
    db = get_db()
    linha = db.execute("SELECT valor FROM definicoes WHERE chave = 'precos_ultima_ronda'").fetchone()
    agora = datetime.now()
    if linha and agora - datetime.fromisoformat(linha[0]) < timedelta(hours=HORAS_ENTRE_RONDAS):
        return
    db.execute("INSERT OR REPLACE INTO definicoes (chave, valor) VALUES ('precos_ultima_ronda', ?)",
               (agora.isoformat(timespec="seconds"),))
    db.commit()

    app = current_app._get_current_object()

    def ronda():
        with app.app_context():
            try:
                atualizar_todos(get_db())
            except Exception:  # um erro aqui nunca deve afetar a app
                app.logger.exception("Erro ao atualizar os preços dos ingredientes")

    threading.Thread(target=ronda, daemon=True).start()
