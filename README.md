# tunneler

Automatically create Cloudflare Tunnels for any process. Tunneler watches your process for listening TCP ports and creates ephemeral tunnels with random subdomains. Everything is cleaned up when the process exits.

```
tunneler run -- uv run main.py --port 8080
```

```
[tunneler] Started process (PID 12345), watching for ports...
Serving HTTP on :: port 8080 ...
[tunneler] ✓ https://swift-owl.example.com → localhost:8080
[tunneler] ▄▄▄▄▄▄▄ ▄▄ ▄▄  ▄  ▄▄ ▄▄▄▄▄▄▄
[tunneler] █ ▄▄▄ █ ▀▄▄▀█▄█▀█▀███ █ ▄▄▄ █
[tunneler] ...
```

## Install

```
uv tool install --from git+https://github.com/obledev/tunneler tunneler
```

Requires [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) to be installed and on your PATH.

## Setup

### 1. Create a Cloudflare API token

Go to [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) and create a custom token with these permissions:

| Scope | Permission | Access |
|-------|-----------|--------|
| Account | Cloudflare Tunnel | Edit |
| Account | Access: Apps and Policies | Edit |
| Zone | DNS | Edit |

The Access permission is only needed if you plan to use `--auth`.

### 2. Initialize tunneler

```
tunneler init
```

This will prompt you for:
- **API token** — the token you just created
- **Zone** — pick which domain to use (fetched automatically from your account)
- **Default auth emails** — optional, used with `--auth` (supports `user@example.com` and `*@company.com` wildcards)

Config is saved to `~/.config/tunneler/config.json`. Run `tunneler init` again to update any setting — everything defaults to the current value.

## Usage

### Basic

```
tunneler run -- <your command>
```

Tunneler starts your command, watches for any TCP ports it listens on, and creates a tunnel for each one. Subdomains are randomly generated (e.g. `ninja-iguana.example.com`) so they can't be guessed.

If your process opens multiple ports, each gets its own tunnel.

### With authentication

```
tunneler run --auth -- <your command>
```

Creates a [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/) application for each tunnel using the default email policy from your config. Visitors must authenticate before they can reach your app.

```
tunneler run --auth-open -- <your command>
```

Same as `--auth`, but also opens the Cloudflare Access dashboard in your browser so you can customize the policy for this specific tunnel.

### With custom subdomain

```
tunneler run --subdomain myapp -- <your command>
```

Use a specific subdomain instead of a randomly generated one. The subdomain will be `myapp.yourdomain.com`. You can also use `--name` as an alias for `--subdomain`.

Note: If your application listens on multiple ports, only the first port will get the custom subdomain. Subsequent ports will fail because a subdomain can only point to one tunnel.

### Cleanup orphaned tunnels

If tunneler is killed without cleanup (e.g. `kill -9`), tunnels and DNS records may be left behind. To remove them:

```
tunneler cleanup
```

This finds all tunnels prefixed with `tunneler-` and their corresponding DNS records, shows them, and asks for confirmation before deleting.
