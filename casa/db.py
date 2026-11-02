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
    4: """
        -- Definições de texto da app (por agora, só o hash da palavra-passe).
        CREATE TABLE definicoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
    """,
    5: """
        -- Tabela de despesas fixas (Netflix, ginásio...), lançadas em cada mês com um botão.
        CREATE TABLE despesas_fixas (
            id INTEGER PRIMARY KEY,
            descricao TEXT NOT NULL,
            categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
            valor REAL NOT NULL,
            dia INTEGER NOT NULL DEFAULT 1,
            ativa INTEGER NOT NULL DEFAULT 1,
            notas TEXT NOT NULL DEFAULT ''
        );
        -- Liga cada gasto lançado à despesa fixa de onde veio (para não a lançar duas vezes no mesmo mês).
        ALTER TABLE gastos ADD COLUMN fixa_id INTEGER REFERENCES despesas_fixas(id) ON DELETE SET NULL;

        -- Passa os gastos que já estavam marcados como fixos para a tabela (com o valor mais recente).
        INSERT INTO despesas_fixas (descricao, categoria_id, valor, dia, notas)
        SELECT g.descricao, g.categoria_id, g.valor, CAST(substr(g.data, 9, 2) AS INTEGER), g.notas
        FROM gastos g
        WHERE g.fixo = 1 AND g.id = (
            SELECT g2.id FROM gastos g2 WHERE g2.fixo = 1 AND lower(g2.descricao) = lower(g.descricao)
            ORDER BY g2.data DESC, g2.id DESC LIMIT 1
        );
        UPDATE gastos SET fixa_id = (
            SELECT f.id FROM despesas_fixas f WHERE lower(f.descricao) = lower(gastos.descricao)
        ) WHERE fixo = 1;
    """,
    6: """
        -- Link do produto no Continente para atualizar o preço dos ingredientes automaticamente.
        ALTER TABLE ingredientes ADD COLUMN link TEXT NOT NULL DEFAULT '';
        ALTER TABLE ingredientes ADD COLUMN verificado_em TEXT;            -- última vez que se foi ver o preço
        ALTER TABLE ingredientes ADD COLUMN aviso_preco TEXT NOT NULL DEFAULT '';  -- problema na última verificação

        CREATE TABLE precos_historico (
            id INTEGER PRIMARY KEY,
            ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            preco REAL NOT NULL
        );
        CREATE INDEX idx_precos_historico ON precos_historico(ingrediente_id, data);
    """,
    7: """
        -- Orçamentos de bolos (massa, recheio, caixa, luz do forno, mão de obra e margem).
        CREATE TABLE orcamentos_bolo (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            cliente TEXT NOT NULL DEFAULT '',
            data_entrega TEXT,
            fatias INTEGER NOT NULL DEFAULT 0,
            dados TEXT NOT NULL,           -- JSON com as receitas, extras e valores usados no cálculo
            custo REAL NOT NULL,
            preco REAL NOT NULL,
            notas TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL DEFAULT (date('now'))
        );
        -- Valores por defeito dos orçamentos (o preço do kWh é o mesmo da impressão 3D).
        INSERT OR IGNORE INTO config (chave, valor) VALUES
            ('bolo_forno_w', 2000), ('bolo_hora_trabalho', 8), ('bolo_margem_pct', 30);
    """,
    8: """
        -- Extras dos bolos com preço definido (caixa, velas...), para escolher nos orçamentos.
        CREATE TABLE extras_bolo (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
            preco REAL NOT NULL DEFAULT 0
        );
        INSERT INTO extras_bolo (nome, preco) VALUES
            ('Caixa', 0), ('Base de cartão', 0), ('Velas', 0), ('Topo de bolo', 0);
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
