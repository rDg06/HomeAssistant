import os
import secrets

from flask import Flask, render_template

from . import db, util


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DATABASE"] = os.path.join(app.instance_path, "casa.db")
    app.config["SECRET_KEY"] = secrets.token_hex()
    app.config.update(config or {})

    db.init_app(app)

    from . import gastos, impressao, receitas

    app.register_blueprint(gastos.bp)
    app.register_blueprint(impressao.bp)
    app.register_blueprint(receitas.bp)

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
            n_receitas=con.execute("SELECT COUNT(*) FROM receitas").fetchone()[0],
            n_ingredientes=con.execute("SELECT COUNT(*) FROM ingredientes").fetchone()[0],
        )

    return app
