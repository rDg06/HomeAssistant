-- Gastos mensais
CREATE TABLE categorias (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE gastos (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
    valor REAL NOT NULL,
    fixo INTEGER NOT NULL DEFAULT 0,
    notas TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_gastos_data ON gastos(data);

INSERT INTO categorias (nome) VALUES
    ('Casa'), ('Supermercado'), ('Contas (luz, água, gás, net)'),
    ('Transportes'), ('Saúde'), ('Lazer'), ('Outros');

-- Impressão 3D
CREATE TABLE config (
    chave TEXT PRIMARY KEY,
    valor REAL NOT NULL
);
INSERT INTO config (chave, valor) VALUES
    ('preco_kwh', 0.16),
    ('potencia_w', 150),
    ('custo_impressora', 350),
    ('vida_util_horas', 5000),
    ('taxa_falha_pct', 10),
    ('valor_hora_trabalho', 5),
    ('margem_pct', 50);

CREATE TABLE filamentos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    material TEXT NOT NULL DEFAULT 'PLA',
    preco_kg REAL NOT NULL
);
INSERT INTO filamentos (nome, material, preco_kg) VALUES ('PLA genérico', 'PLA', 20);

CREATE TABLE pecas (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    filamento_id INTEGER REFERENCES filamentos(id) ON DELETE SET NULL,
    gramas REAL NOT NULL DEFAULT 0,
    horas REAL NOT NULL DEFAULT 0,
    horas_trabalho REAL NOT NULL DEFAULT 0,
    custos_extra REAL NOT NULL DEFAULT 0,
    preco_venda REAL,
    notas TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT (date('now'))
);

-- O custo unitário fica gravado na venda para o lucro não mudar se os preços mudarem depois.
CREATE TABLE vendas (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    peca_id INTEGER REFERENCES pecas(id) ON DELETE SET NULL,
    descricao TEXT NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 1,
    preco_unit REAL NOT NULL,
    custo_unit REAL NOT NULL DEFAULT 0,
    outros_custos REAL NOT NULL DEFAULT 0,
    cliente TEXT NOT NULL DEFAULT '',
    notas TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_vendas_data ON vendas(data);

-- Receitas
CREATE TABLE ingredientes (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
    unidade TEXT NOT NULL DEFAULT 'g',
    qtd_embalagem REAL NOT NULL CHECK (qtd_embalagem > 0),
    preco_embalagem REAL NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL DEFAULT (date('now'))
);
INSERT INTO ingredientes (nome, unidade, qtd_embalagem, preco_embalagem) VALUES
    ('Farinha', 'g', 1000, 0.89),
    ('Açúcar', 'g', 1000, 1.19),
    ('Ovos', 'un', 12, 2.99),
    ('Manteiga', 'g', 250, 2.49),
    ('Leite', 'ml', 1000, 0.85),
    ('Fermento em pó', 'g', 45, 0.99);

CREATE TABLE receitas (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'Base',
    porcoes INTEGER NOT NULL DEFAULT 1,
    tamanho TEXT NOT NULL DEFAULT '',
    preparo TEXT NOT NULL DEFAULT '',
    notas TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE receita_ingredientes (
    id INTEGER PRIMARY KEY,
    receita_id INTEGER NOT NULL REFERENCES receitas(id) ON DELETE CASCADE,
    ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id) ON DELETE RESTRICT,
    quantidade REAL NOT NULL
);
