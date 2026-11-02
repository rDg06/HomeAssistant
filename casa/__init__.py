import os
import secrets
from datetime import timedelta

from flask import Flask, render_template

from . import db, util


def _chave_secreta(app):
    """Chave que assina o cookie da sessão. Fica guardada para as sessões sobreviverem a reinícios."""
    caminho = os.path.join(app.instance_path, "chave_secreta")
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as ficheiro:
            ficheiro.write(secrets.token_hex(32))
    with open(caminho, encoding="utf-8") as ficheiro:
        return ficheiro.read().strip()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DATABASE"] = os.path.join(app.instance_path, "casa.db")
    app.config["SECRET_KEY"] = _chave_secreta(app)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config.update(config or {})

    db.init_app(app)

    from . import auth, backup, gastos, impressao, receitas

    app.register_blueprint(auth.bp)
    app.before_request(auth.proteger)
    app.before_request(lambda: backup.verificar(app))  # cópia de segurança semanal
    app.register_blueprint(gastos.bp)
    app.register_blueprint(impressao.bp)
    app.register_blueprint(receitas.bp)

    # Páginas de erro em português e com o aspeto da app (também no telemóvel).
    ERROS = {
        400: ("Pedido inválido", "Alguma coisa no pedido não estava certa. Volta atrás e tenta outra vez."),
        404: ("Página não encontrada", "Esta página não existe ou o registo já foi apagado."),
        405: ("Pedido inválido", "Esta página não pode ser aberta assim. Volta atrás e tenta outra vez."),
        500: ("Ocorreu um erro", "Algo correu mal na app. Tenta outra vez daqui a pouco."),
    }

    def pagina_de_erro(codigo):
        titulo, mensagem = ERROS[codigo]
        return render_template("erro.html", titulo=titulo, mensagem=mensagem), codigo

    for codigo in ERROS:
        app.register_error_handler(codigo, lambda erro, codigo=codigo: pagina_de_erro(codigo))

    @app.errorhandler(OverflowError)
    def numero_grande_demais(erro):
        # Um id ou número absurdo (ex.: /gastos/99999999999999999999/editar) não cabe no SQLite.
        return pagina_de_erro(400)

    for filtro in (util.eur, util.num, util.data_curta, util.duracao):
        app.add_template_filter(filtro)
    app.jinja_env.globals["nome_mes"] = util.nome_mes

    @app.route("/")
    def inicio():
        con = db.get_db()
        mes = util.hoje_mes()
        mes_gastos = gastos.mes_atual()
        return render_template(
            "inicio.html",
            mes=mes,
            mes_gastos=mes_gastos,
            gastos_mes=gastos.total_mes(con, mes_gastos),
            rendimentos_mes=gastos.total_mes(con, mes_gastos, "rendimentos"),
            vendas=impressao.resumo_vendas(con, mes),
            # Bolos do mês: orçamentos com entrega neste mês (ou feitos neste mês, se não tiverem data).
            bolos=con.execute(
                """SELECT COUNT(*) AS n, COALESCE(SUM(preco), 0) AS total, COALESCE(SUM(preco - custo), 0) AS lucro
                   FROM orcamentos_bolo WHERE substr(COALESCE(data_entrega, criado_em), 1, 7) = ?""",
                (mes,),
            ).fetchone(),
        )

    return app
