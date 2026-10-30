# Casa

Pequena app para as coisas cá de casa:

- **Gastos mensais**: registo por categoria, resumo do mês, comparação com o mês anterior e cópia dos gastos fixos.
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
