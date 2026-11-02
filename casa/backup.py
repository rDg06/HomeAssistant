"""Cópia de segurança semanal da base de dados.

Enquanto a app está a correr, vê de hora a hora se a última cópia tem mais de 7 dias e, se tiver, faz uma
nova em segundo plano. Ficam guardadas as 8 cópias mais recentes (cerca de dois meses).

As cópias vão para `instance/backups`, ou para a pasta na variável de ambiente CASA_BACKUPS
(por exemplo uma pasta do OneDrive, para ficarem também fora deste PC).
"""
import os
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta

DIAS_ENTRE_COPIAS = 7
COPIAS_A_MANTER = 8
SEGUNDOS_ENTRE_VERIFICACOES = 3600
PREFIXO = "casa-"

_trinco = threading.Lock()
_ultima_verificacao = 0.0


def pasta(app):
    return os.environ.get("CASA_BACKUPS") or os.path.join(app.instance_path, "backups")


def copias(app):
    """Cópias existentes, da mais recente para a mais antiga (caminhos completos)."""
    destino = pasta(app)
    if not os.path.isdir(destino):
        return []
    nomes = sorted((n for n in os.listdir(destino) if n.startswith(PREFIXO) and n.endswith(".db")), reverse=True)
    return [os.path.join(destino, n) for n in nomes]


def fazer_copia(app):
    """Copia a base de dados (de forma segura, mesmo com a app a escrever) e apaga as cópias mais antigas."""
    destino = pasta(app)
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, f"{PREFIXO}{date.today().isoformat()}.db")
    temporario = caminho + ".parcial"
    origem = sqlite3.connect(app.config["DATABASE"])
    try:
        copia = sqlite3.connect(temporario)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()
    os.replace(temporario, caminho)  # só aparece com o nome final quando está completa
    for antiga in copias(app)[COPIAS_A_MANTER:]:
        os.remove(antiga)
    return caminho


def precisa_de_copia(app):
    existentes = copias(app)
    if not existentes:
        return True
    feita_em = datetime.fromtimestamp(os.path.getmtime(existentes[0]))
    return datetime.now() - feita_em >= timedelta(days=DIAS_ENTRE_COPIAS)


def verificar(app):
    """Chamado antes de cada pedido: no máximo uma verificação por hora, a cópia é feita noutra thread."""
    global _ultima_verificacao
    if app.config.get("TESTING") or time.monotonic() - _ultima_verificacao < SEGUNDOS_ENTRE_VERIFICACOES:
        return
    if not _trinco.acquire(blocking=False):
        return  # já há uma cópia a ser feita
    _ultima_verificacao = time.monotonic()

    def tarefa():
        try:
            if precisa_de_copia(app):
                app.logger.info("Cópia de segurança feita em %s", fazer_copia(app))
        except Exception:  # um erro aqui nunca deve afetar a app
            app.logger.exception("Erro ao fazer a cópia de segurança")
        finally:
            _trinco.release()

    threading.Thread(target=tarefa, daemon=True).start()
