import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")

# Alterações à base de dados depois da versão 1, aplicadas por ordem a bases de dados já existentes.
MIGRACOES = {
    2: """
        -- Valores da calculadora da Bambu Lab A1 (só muda os que ainda estão nos valores iniciais).
        INSERT OR IGNORE INTO config (chave, valor) VALUES ('prep_min', 10), ('manutencao_hora', 0.06);
        UPDATE config SET valor = 0.22 WHERE chave = 'preco_kwh' AND valor = 0.16;
        UPDATE config SET valor = 100 WHERE chave = 'potencia_w' AND valor = 150;
        UPDATE config SET valor = 420 WHERE chave = 'custo_impressora' AND valor = 350;
        UPDATE config SET valor = 10 WHERE chave = 'valor_hora_trabalho' AND valor = 5;
        UPDATE filamentos SET preco_kg = 15 WHERE nome = 'PLA genérico' AND preco_kg = 20;
    """,
    3: """
        -- Rendimentos mensais (salários, cartão refeição...) de cada pessoa da casa.
        CREATE TABLE rendimentos (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            pessoa TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'Salário',
            valor REAL NOT NULL,
            fixo INTEGER NOT NULL DEFAULT 1,
            notas TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX idx_rendimentos_data ON rendimentos(data);
    """,
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def init_db(app):
    """Cria as tabelas quando a base de dados é nova e aplica as migrações que faltarem."""
    con = sqlite3.connect(app.config["DATABASE"])
    try:
        versao = con.execute("PRAGMA user_version").fetchone()[0]
        if versao < 1:
            con.executescript(SCHEMA.read_text(encoding="utf-8"))
            con.execute("PRAGMA user_version = 1")
            versao = 1
        for numero in sorted(MIGRACOES):
            if versao < numero:
                con.executescript(MIGRACOES[numero])
                con.execute(f"PRAGMA user_version = {numero}")
        con.commit()
    finally:
        con.close()


def init_app(app):
    init_db(app)
    app.teardown_appcontext(close_db)
