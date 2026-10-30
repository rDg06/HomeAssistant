import math
import re
import unicodedata
from datetime import date

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def parse_num(valor, padrao=0.0):
    """Lê números escritos com vírgula ou ponto ("1,5", "1.234,50", "2.5")."""
    if valor is None:
        return padrao
    valor = str(valor).strip().replace("€", "").replace(" ", "")
    if not valor:
        return padrao
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        numero = float(valor)
    except ValueError:
        return padrao
    # "inf", "nan" e números enormes não são valores válidos para dinheiro ou quantidades.
    return numero if math.isfinite(numero) and abs(numero) < 1e12 else padrao


def sem_acentos(texto):
    """Para pesquisas: "Pão de Ló" e "pao de lo" ficam iguais."""
    normal = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in normal if not unicodedata.combining(c))


def data_valida(texto):
    try:
        return date.fromisoformat(texto or "").isoformat()
    except ValueError:
        return None


def _formatar(valor, casas):
    return f"{valor:,.{casas}f}".replace(",", " ").replace(".", ",")


def eur(valor):
    return _formatar(valor or 0, 2) + " €"


def num(valor, casas=2):
    texto = _formatar(valor or 0, casas)
    if "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return texto


def data_curta(iso):
    return f"{iso[8:10]}/{iso[5:7]}" if iso else ""


def duracao(horas):
    h, m = divmod(round((horas or 0) * 60), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def hoje_mes():
    return date.today().strftime("%Y-%m")


def mes_valido(mes):
    return bool(re.fullmatch(r"(19|20)\d\d-(0[1-9]|1[0-2])", mes or ""))


def existe(db, tabela, id):
    """Devolve o id se existir na tabela (ex.: uma categoria apagada noutro separador), senão None."""
    if id is None:
        return None
    return id if db.execute(f"SELECT 1 FROM {tabela} WHERE id = ?", (id,)).fetchone() else None


def deslocar_mes(mes, n):
    ano, m = map(int, mes.split("-"))
    indice = ano * 12 + (m - 1) + n
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def nome_mes(mes, curto=False):
    ano, m = map(int, mes.split("-"))
    if curto:
        return f"{MESES_CURTOS[m - 1]} {ano % 100:02d}"
    return f"{MESES[m - 1]} {ano}"
