import sys

from casa import create_app

app = create_app()

if __name__ == "__main__":
    # Em modo debug fica só acessível neste PC; normalmente fica aberto à rede de casa.
    debug = "--debug" in sys.argv
    app.run(host="127.0.0.1" if debug else "0.0.0.0", port=5000, debug=debug)
