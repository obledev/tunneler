import sys

import qrcode

PREFIX = "\033[36m[tunneler]\033[0m"


def log(msg: str) -> None:
    print(f"{PREFIX} {msg}", file=sys.stderr, flush=True)


def log_tunnel_up(hostname: str, port: int) -> None:
    url = f"https://{hostname}"
    log(f"✓ {url} → localhost:{port}")
    _print_qr(url)


def log_tunnel_down(hostname: str) -> None:
    log(f"✗ https://{hostname} removed")


def _print_qr(url: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)

    # Use Unicode half-block characters for compact terminal QR
    modules = qr.get_matrix()
    lines = []
    for r in range(0, len(modules) - 1, 2):
        line = ""
        for c in range(len(modules[r])):
            top = modules[r][c]
            bot = modules[r + 1][c]
            if top and bot:
                line += "█"
            elif top and not bot:
                line += "▀"
            elif not top and bot:
                line += "▄"
            else:
                line += " "
        lines.append(line)
    if len(modules) % 2:
        line = ""
        for c in range(len(modules[-1])):
            line += "▀" if modules[-1][c] else " "
        lines.append(line)

    for line in lines:
        print(f"{PREFIX} {line}", file=sys.stderr, flush=True)
