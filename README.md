# Casa

Pequena app para as coisas cá de casa:

- **Gastos mensais**: registo por categoria (a partir de Novembro de 2026), gráfico por categoria, rendimentos do Rodrigo e da Carina, saldo do mês e cópia dos registos fixos.
- **Impressão 3D**: calculadora de custo (filamento, eletricidade, desgaste, falhas, trabalho), peças guardadas e registo de vendas com lucro.
- **Receitas**: ingredientes com preço de embalagem, custo total e por porção de cada receita (bases, recheios, coberturas), com multiplicador de quantidades.

Feita em Python + Flask. Os dados ficam em `instance/casa.db` (SQLite). Para fazer uma cópia de segurança basta copiar esse ficheiro.

## Como arrancar

Precisas do Python 3.10 ou mais recente.

No Windows basta dar dois cliques em `iniciar.bat`. Da primeira vez prepara o ambiente e instala o Flask.

Ou manualmente:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
```

Abre http://localhost:5000. No telemóvel, ligado à mesma rede Wi-Fi, usa `http://<ip-do-pc>:5000`
(o IP vê-se com `ipconfig`). O Windows pode pedir para permitir o Python na firewall.

Para desenvolver com recarregamento automático: `.venv\Scripts\python run.py --debug` (só fica acessível neste PC).

## Palavra-passe

A app está protegida por uma palavra-passe da casa. Da primeira vez que a abres, pede-te para a criar.
Cada aparelho fica com a sessão aberta durante 30 dias. Para a mudar, usa "Mudar passe" no topo da página;
os outros aparelhos têm de voltar a entrar.

Se te esqueceres dela, para a app e corre:

```bash
.venv\Scripts\python run.py --repor-passe
```

Na próxima visita a app pede uma palavra-passe nova. Os dados não são apagados.
