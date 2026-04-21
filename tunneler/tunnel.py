import json
import subprocess
import tempfile
from pathlib import Path

import yaml

from .cloudflare import CloudflareClient
from .names import generate_name
from .output import log, log_tunnel_down, log_tunnel_up


class TunnelManager:
    def __init__(self, client: CloudflareClient):
        self.client = client
        self._active: dict[int, dict] = {}  # port -> {tunnel_id, dns_record_id, process}

    @property
    def active_ports(self) -> set[int]:
        return set(self._active.keys())

    def start_tunnel(self, port: int) -> None:
        for _ in range(10):
            subdomain = generate_name()
            name = f"tunneler-{subdomain}"
            try:
                tunnel = self.client.create_tunnel(name)
                break
            except Exception:
                continue
        else:
            raise RuntimeError("Failed to create tunnel after 10 attempts")
        tunnel_id = tunnel["id"]

        dns_record_id = self.client.create_dns_record(subdomain, tunnel_id)

        credentials = {
            "AccountTag": self.client.account_id,
            "TunnelID": tunnel_id,
            "TunnelSecret": tunnel["secret"],
        }
        creds_file = Path(tempfile.mktemp(suffix=".json", prefix=f"tunneler-{port}-"))
        creds_file.write_text(json.dumps(credentials))

        hostname = f"{subdomain}.{self.client.domain}"
        config = {
            "tunnel": tunnel_id,
            "credentials-file": str(creds_file),
            "ingress": [
                {"hostname": hostname, "service": f"http://localhost:{port}"},
                {"service": "http_status:404"},
            ],
        }
        config_file = Path(tempfile.mktemp(suffix=".yaml", prefix=f"tunneler-{port}-"))
        config_file.write_text(yaml.dump(config))

        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--config", str(config_file), "run"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._active[port] = {
            "tunnel_id": tunnel_id,
            "dns_record_id": dns_record_id,
            "hostname": hostname,
            "process": proc,
            "creds_file": creds_file,
            "config_file": config_file,
        }
        log_tunnel_up(hostname, port)

    def stop_tunnel(self, port: int) -> None:
        info = self._active.pop(port, None)
        if not info:
            return
        proc = info["process"]
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        try:
            self.client.delete_dns_record(info["dns_record_id"])
        except Exception:
            pass
        try:
            self.client.delete_tunnel(info["tunnel_id"])
        except Exception:
            pass

        info["creds_file"].unlink(missing_ok=True)
        info["config_file"].unlink(missing_ok=True)
        log_tunnel_down(info["hostname"])

    def stop_all(self) -> None:
        for port in list(self._active.keys()):
            self.stop_tunnel(port)
