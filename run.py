import sys

from casa import create_app
from casa.auth import repor_passe

app = create_app()

if __name__ == "__main__":
    if "--repor-passe" in sys.argv:
        repor_passe(app)
        print("Palavra-passe apagada. Abre a app para criar uma nova.")
        sys.exit()
    # Em modo debug fica só acessível neste PC; normalmente fica aberto à rede de casa.
    debug = "--debug" in sys.argv
    app.run(host="127.0.0.1" if debug else "0.0.0.0", port=5000, debug=debug)
