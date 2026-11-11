import socket
import sys

from casa import create_app
from casa.auth import repor_passe
from casa.backup import fazer_copia

PORTA = 5000

app = create_app()


def ip_na_rede():
    """IP deste PC na rede de casa (para abrir a app no telemóvel). Não envia nada pela rede."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 1))
            return s.getsockname()[0]
    except OSError:
        return None


if __name__ == "__main__":
    if "--repor-passe" in sys.argv:
        repor_passe(app)
        print("Palavra-passe apagada. Abre a app para criar uma nova.")
        sys.exit()
    if "--backup" in sys.argv:
        falhou = False
        for pasta, caminho, erro in fazer_copia(app):
            if erro:
                falhou = True
                print(f"ERRO em {pasta}: {erro}")
            else:
                print(f"Cópia feita: {caminho}")
        sys.exit(1 if falhou else 0)
    if "--debug" in sys.argv:
        # Recarrega sozinho quando o código muda; só fica acessível neste PC.
        app.run(host="127.0.0.1", port=PORTA, debug=True)
        sys.exit()

    from waitress import serve

    # No Windows dois servidores podem ficar na mesma porta sem dar erro, por isso confirma-se antes.
    with socket.socket() as s:
        s.settimeout(1)
        if s.connect_ex(("127.0.0.1", PORTA)) == 0:
            print(f"A app já está a correr noutra janela (porta {PORTA} ocupada).", flush=True)
            sys.exit(1)

    print(f"A app está a correr em http://localhost:{PORTA}", flush=True)
    if ip := ip_na_rede():
        print(f"No telemóvel (mesmo Wi-Fi): http://{ip}:{PORTA}", flush=True)
    serve(app, host="0.0.0.0", port=PORTA, threads=8)
