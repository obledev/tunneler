import httpx

API_BASE = "https://api.cloudflare.com/client/v4"


def fetch_zones(api_token: str) -> list[dict]:
    client = httpx.Client(
        base_url=API_BASE,
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=30,
    )
    resp = client.get("/zones", params={"per_page": 50})
    resp.raise_for_status()
    return resp.json()["result"]


class CloudflareClient:
    def __init__(self, api_token: str, account_id: str, zone_id: str, domain: str):
        self.domain = domain
        self.account_id = account_id
        self.zone_id = zone_id
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=30,
        )

    def create_tunnel(self, name: str) -> dict:
        import base64
        import os

        secret_bytes = os.urandom(32)
        secret_b64 = base64.b64encode(secret_bytes).decode()
        resp = self._client.post(
            f"/accounts/{self.account_id}/cfd_tunnel",
            json={"name": name, "tunnel_secret": secret_b64},
        )
        resp.raise_for_status()
        data = resp.json()["result"]
        data["secret"] = secret_b64
        return data

    def delete_tunnel(self, tunnel_id: str) -> None:
        self._client.delete(
            f"/accounts/{self.account_id}/cfd_tunnel/{tunnel_id}",
            params={"cascade": "true"},
        )

    def create_dns_record(self, subdomain: str, tunnel_id: str) -> str:
        hostname = f"{subdomain}.{self.domain}"
        resp = self._client.post(
            f"/zones/{self.zone_id}/dns_records",
            json={
                "type": "CNAME",
                "name": hostname,
                "content": f"{tunnel_id}.cfargotunnel.com",
                "proxied": True,
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]["id"]

    def delete_dns_record(self, record_id: str) -> None:
        self._client.delete(f"/zones/{self.zone_id}/dns_records/{record_id}")

    def list_tunnels(self, name_prefix: str = "") -> list[dict]:
        params = {"is_deleted": "false"}
        if name_prefix:
            params["name"] = name_prefix
        resp = self._client.get(
            f"/accounts/{self.account_id}/cfd_tunnel", params=params
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def list_dns_records(self) -> list[dict]:
        resp = self._client.get(
            f"/zones/{self.zone_id}/dns_records",
            params={"type": "CNAME", "content": "cfargotunnel.com", "match": "any"},
        )
        resp.raise_for_status()
        return resp.json()["result"]
