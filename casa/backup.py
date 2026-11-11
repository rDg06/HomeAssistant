"""Cópia de segurança semanal da base de dados, em uma ou mais pastas (por exemplo uma em cada disco).

Enquanto a app está a correr, vê de hora a hora se a última cópia de cada pasta tem mais de 7 dias e, se
tiver, faz uma nova em segundo plano. Em cada pasta ficam as 8 cópias mais recentes (cerca de dois meses).
Cada pasta é tratada à parte: se um disco não estiver disponível, as outras cópias são feitas na mesma.

As pastas são, por esta ordem de preferência:
  1. a variável de ambiente CASA_BACKUPS (várias pastas separadas por ";");
  2. o ficheiro instance/pastas_backup.txt (uma pasta por linha; linhas começadas por # são ignoradas);
  3. instance/backups.
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
FICHEIRO_PASTAS = "pastas_backup.txt"

_trinco = threading.Lock()
_ultima_verificacao = 0.0


def pastas(app):
    """Pastas onde guardar as cópias (caminhos completos, sem repetidos)."""
    lista = [p for p in os.environ.get("CASA_BACKUPS", "").split(";") if p.strip()]
    ficheiro = os.path.join(app.instance_path, FICHEIRO_PASTAS)
    if not lista and os.path.exists(ficheiro):
        with open(ficheiro, encoding="utf-8-sig") as f:
            lista = [linha for linha in f.read().splitlines() if linha.strip() and not linha.lstrip().startswith("#")]
    if not lista:
        lista = [os.path.join(app.instance_path, "backups")]
    unicas = []
    for p in lista:
        p = os.path.abspath(os.path.expandvars(p.strip().strip('"')))
        if os.path.normcase(p) not in map(os.path.normcase, unicas):
            unicas.append(p)
    return unicas


def pastas_da_variavel():
    """True quando as pastas vêm da variável de ambiente (e por isso não se mudam na página)."""
    return bool(os.environ.get("CASA_BACKUPS", "").strip(" ;"))


def guardar_pastas(app, lista):
    """Grava as pastas no ficheiro. Sem pastas, apaga o ficheiro e volta-se a usar instance/backups."""
    ficheiro = os.path.join(app.instance_path, FICHEIRO_PASTAS)
    if lista:
        with open(ficheiro, "w", encoding="utf-8") as f:
            f.write("# Pastas das cópias de segurança (uma por linha). Muda-se em Configurações.\n")
            f.write("\n".join(lista) + "\n")
    elif os.path.exists(ficheiro):
        os.remove(ficheiro)


def problema_na_pasta(pasta):
    """Confirma que dá para escrever na pasta (criando-a se for preciso). Devolve o problema ou None."""
    if not os.path.isabs(pasta):
        return "Escreve o caminho completo da pasta, com a letra do disco (ex.: D:\\Backups Casa)."
    teste = os.path.join(pasta, ".teste-escrita")
    try:
        os.makedirs(pasta, exist_ok=True)
        with open(teste, "w") as f:
            f.write("ok")
        os.remove(teste)
    except OSError as erro:
        return f"Não dá para escrever nessa pasta ({erro.strerror or erro})."
    return None


def estado(pasta):
    """Para a página de configurações: se a pasta está acessível, quantas cópias tem e a data da última."""
    existentes = copias(pasta)
    return {
        "pasta": pasta,
        "acessivel": os.path.isdir(pasta),
        "n": len(existentes),
        "ultima": datetime.fromtimestamp(os.path.getmtime(existentes[0])) if existentes else None,
    }


def copias(pasta):
    """Cópias existentes numa pasta, da mais recente para a mais antiga (caminhos completos)."""
    if not os.path.isdir(pasta):
        return []
    nomes = sorted((n for n in os.listdir(pasta) if n.startswith(PREFIXO) and n.endswith(".db")), reverse=True)
    return [os.path.join(pasta, n) for n in nomes]


def copiar_para(app, pasta):
    """Copia a base de dados para uma pasta (de forma segura, mesmo com a app a escrever) e apaga as
    cópias mais antigas dessa pasta. Devolve o caminho da cópia."""
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{PREFIXO}{date.today().isoformat()}.db")
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
    for antiga in copias(pasta)[COPIAS_A_MANTER:]:
        os.remove(antiga)
    return caminho


def fazer_copia(app, so_desatualizadas=False):
    """Faz a cópia em todas as pastas (ou só nas que têm a última cópia com mais de 7 dias).
    Devolve uma lista de (pasta, caminho da cópia ou None, erro ou None)."""
    resultados = []
    for pasta in pastas(app):
        if so_desatualizadas and not precisa_de_copia(pasta):
            continue
        try:
            resultados.append((pasta, copiar_para(app, pasta), None))
        except (OSError, sqlite3.Error) as erro:  # ex.: o disco não está ligado ou não há espaço
            resultados.append((pasta, None, erro))
            try:
                os.remove(os.path.join(pasta, f"{PREFIXO}{date.today().isoformat()}.db.parcial"))
            except OSError:
                pass
    return resultados


def precisa_de_copia(pasta):
    existentes = copias(pasta)
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
            for pasta, caminho, erro in fazer_copia(app, so_desatualizadas=True):
                if erro:
                    app.logger.error("Não foi possível fazer a cópia de segurança em %s: %s", pasta, erro)
                else:
                    app.logger.info("Cópia de segurança feita em %s", caminho)
        except Exception:  # um erro aqui nunca deve afetar a app
            app.logger.exception("Erro ao fazer a cópia de segurança")
        finally:
            _trinco.release()

    threading.Thread(target=tarefa, daemon=True).start()
