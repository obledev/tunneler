import atexit
import signal
import subprocess
import sys
import time

import click

from .cloudflare import CloudflareClient, fetch_zones
from .config import CONFIG_FILE, load_config, save_config
from .monitor import get_listening_ports
from .output import log
from .tunnel import TunnelManager

POLL_INTERVAL = 0.5


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
def init():
    """Initialize tunneler configuration."""
    click.echo("Tunneler configuration")
    click.echo("=" * 40)
    api_token = click.prompt("Cloudflare API token")

    click.echo("\nFetching zones...")
    zones = fetch_zones(api_token)
    if not zones:
        click.echo("No zones found for this token.", err=True)
        sys.exit(1)

    for i, zone in enumerate(zones, 1):
        click.echo(f"  {i}. {zone['name']}")

    choice = click.prompt("Select zone", type=click.IntRange(1, len(zones)))
    selected = zones[choice - 1]
    account_id = selected["account"]["id"]

    config = {
        "api_token": api_token,
        "account_id": account_id,
        "zone_id": selected["id"],
        "domain": selected["name"],
    }
    save_config(config)
    click.echo(f"\nConfig saved to {CONFIG_FILE}")


@main.command(context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1, required=True)
def run(command):
    """Run a command and automatically tunnel its ports.

    Usage: tunneler run -- uv run main.py --port 8080
    """
    config = load_config()
    if not config:
        click.echo("No config found. Run `tunneler init` first.", err=True)
        sys.exit(1)

    client = CloudflareClient(
        api_token=config["api_token"],
        account_id=config["account_id"],
        zone_id=config["zone_id"],
        domain=config["domain"],
    )
    manager = TunnelManager(client)

    proc = subprocess.Popen(
        command,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def cleanup(*_):
        log("Shutting down tunnels...")
        manager.stop_all()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    atexit.register(manager.stop_all)

    log(f"Started process (PID {proc.pid}), watching for ports...")

    while proc.poll() is None:
        current_ports = get_listening_ports(proc.pid)
        new_ports = current_ports - manager.active_ports
        gone_ports = manager.active_ports - current_ports

        for port in new_ports:
            try:
                manager.start_tunnel(port)
            except Exception as e:
                log(f"Failed to tunnel port {port}: {e}")

        for port in gone_ports:
            manager.stop_tunnel(port)

        time.sleep(POLL_INTERVAL)

    log("Process exited, cleaning up...")
    manager.stop_all()
    sys.exit(proc.returncode)


@main.command()
def cleanup():
    """Remove orphaned tunnels and DNS records."""
    config = load_config()
    if not config:
        click.echo("No config found. Run `tunneler init` first.", err=True)
        sys.exit(1)

    client = CloudflareClient(
        api_token=config["api_token"],
        account_id=config["account_id"],
        zone_id=config["zone_id"],
        domain=config["domain"],
    )

    tunnels = client.list_tunnels()
    orphans = [t for t in tunnels if t["name"].startswith("tunneler-")]

    if not orphans:
        click.echo("No orphaned tunnels found.")
        return

    click.echo(f"Found {len(orphans)} orphaned tunnel(s):")
    for t in orphans:
        click.echo(f"  - {t['name']} ({t['id']})")

    if not click.confirm("Remove them?"):
        return

    for t in orphans:
        port = t["name"].removeprefix("tunneler-")
        # Try to find and remove corresponding DNS record
        records = client.list_dns_records()
        for r in records:
            if r["name"] == f"{port}.{config['domain']}":
                client.delete_dns_record(r["id"])
                click.echo(f"  Removed DNS: {r['name']}")
        client.delete_tunnel(t["id"])
        click.echo(f"  Removed tunnel: {t['name']}")

    click.echo("Done.")
