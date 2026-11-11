# Casa

App para as coisas cá de casa, feita para usar no computador e no telemóvel:

- **Gastos**: gastos do mês por categoria (a partir de Novembro de 2026), gráfico por categoria, rendimentos
  do Rodrigo e da Carina (salário, cartão refeição e extra), saldo do mês, despesas fixas (Netflix, ginásio...)
  lançadas com um botão, e categorias editáveis.
- **Impressão 3D**: calculadora de custo igual à folha da Bambu Lab A1 (filamento, eletricidade, desgaste,
  falhas, mão de obra e margem), peças guardadas, orçamento com vários pedidos e registo de vendas com lucro.
- **DeliciArt**:
  - **Orçamentos de bolos**: massa, recheio e cobertura a partir das receitas, caixa e decoração, luz do forno,
    mão de obra e margem, com preço por fatia, texto para enviar ao cliente e resumo por mês.
  - **Receitas** com o custo total e por porção.
  - **Ingredientes e preços**: com o link do produto no Continente, o preço é atualizado sozinho uma vez
    por mês. Os extras dos bolos (caixa, velas...) também têm aqui o seu preço.

Feita em Python + Flask. Os dados ficam em `instance/casa.db` (SQLite), que não vai para o GitHub.

## Como arrancar

Precisas do Python 3.10 ou mais recente ([python.org](https://www.python.org/downloads/)).

No Windows dá dois cliques em **`iniciar.bat`**. Da primeira vez prepara tudo sozinho; depois abre o browser
na app. A janela preta tem de ficar aberta (pode ficar minimizada): fechá-la desliga a app.

Para a app **arrancar sozinha com o Windows**, dá dois cliques em `arrancar-com-o-windows.bat`
(para desfazer: `arrancar-com-o-windows.bat remover`).

Manualmente:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
```

Para desenvolver com recarregamento automático: `.venv\Scripts\python run.py --debug` (só neste PC).

## No telemóvel

Com o telemóvel no mesmo Wi-Fi, abre o endereço que aparece na janela da app (`http://<ip-do-pc>:5000`).
Dá para o pôr no ecrã principal: no menu do browser, "Adicionar ao ecrã principal".

Se o telemóvel não conseguir abrir a app, é a firewall do Windows: em "Firewall do Windows Defender com
Segurança Avançada" → Regras de Entrada, desativa as regras **python.exe** que estejam a **Bloquear**
e permite o Python nas redes privadas.

## Atualizar

Depois de mudanças no código (por exemplo com `git pull`), fecha a janela da app e volta a abrir
`iniciar.bat`. Os pacotes novos são instalados e a base de dados é atualizada sozinha, sem perder dados.

## Palavra-passe

A app está protegida por uma palavra-passe da casa. Da primeira vez que a abres, pede-te para a criar.
Cada aparelho fica com a sessão aberta durante 30 dias. Para a mudar, vai a **⚙ Configurações** no topo da página;
os outros aparelhos têm de voltar a entrar.

Depois de 5 tentativas erradas seguidas, esse aparelho fica 15 minutos sem poder tentar (os outros não são
afetados). Para desbloquear logo, basta fechar e voltar a abrir a app.

Se te esqueceres dela, fecha a app e corre:

```bash
.venv\Scripts\python run.py --repor-passe
```

Na próxima visita a app pede uma palavra-passe nova. Os dados não são apagados.

## Cópias de segurança

Enquanto a app está a correr, faz sozinha uma cópia da base de dados **uma vez por semana**
(ficheiros `casa-AAAA-MM-DD.db`). Em cada pasta ficam as 8 cópias mais recentes, cerca de dois meses.

Por defeito as cópias vão para `instance/backups`. Para as guardar **em dois discos** (por exemplo o SSD e o
disco rígido do PC), vai a **⚙ Configurações** no topo da app e junta uma pasta de cada disco
(ex.: `D:\Backups Casa`). Lá vês também a data da última cópia de cada pasta e há um botão
"Fazer cópia agora". As pastas ficam gravadas em `instance/pastas_backup.txt`.

Cada pasta é tratada à parte: se um disco falhar ou não estiver disponível, a cópia no outro é feita na mesma
(e a que faltou é feita assim que o disco voltar). Também pode ser uma pasta do OneDrive.

Também dá para fazer uma cópia pela linha de comandos:

```bash
.venv\Scripts\python run.py --backup
```

Para recuperar uma cópia: fecha a app, substitui `instance/casa.db` pelo ficheiro da cópia e volta a arrancar.
