#!/usr/bin/env python3
"""
Linguard CLI - Command Line Interface for Linguard VPN Manager

Usage:
    linguard <command> [options]
    
Commands:
    auth         Authentication commands
    servers      Server management commands
    peers        Peer management commands
    backups      Backup/restore commands
    settings     Settings management
    status       System status
    help         Show help message
"""

import click
import subprocess
import sys
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import necessary modules
try:
    import httpx
    # requests is deprecated in favor of httpx
    try:
        import requests
    except ImportError:
        requests = None
    
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    click.echo("Error: Required packages not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

# Configuration
BASE_URL = os.getenv("LINGUARD_API_URL", "http://localhost:8000")
API_VERSION = "/api/v1"
AUTH_TOKEN = os.getenv("LINGUARD_API_TOKEN")


def api_request(method: str, url: str, **kwargs):
    """Perform an HTTP request against the Linguard API, following redirects.

    httpx does not follow redirects by default, which breaks commands when the
    API answers with a 307 (e.g. trailing-slash normalization).
    """
    kwargs.setdefault("timeout", 10.0)
    return httpx.request(method, url, follow_redirects=True, **kwargs)


def extract_items(data):
    """Normalize collection responses.

    Most collection endpoints return a plain JSON list; some return a
    paginated object with an ``items`` key. Accept both shapes.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def get_headers() -> dict:
    """Get authentication headers."""
    if AUTH_TOKEN:
        return {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }
    return {"Content-Type": "application/json"}


def check_api_health() -> bool:
    """Check if the API is available."""
    try:
        response = api_request("GET", f"{BASE_URL}/health", timeout=10.0)
        return response.status_code == 200
    except Exception as e:
        click.echo(f"Error: Cannot connect to API at {BASE_URL} - {e}", err=True)
        return False


@click.group()
@click.option("--base-url", default=None, help="API base URL (env: LINGUARD_API_URL, default: http://localhost:8000)")
@click.option("--token", default=None, help="API authentication token (env: LINGUARD_API_TOKEN)")
@click.option("--env-file", type=Path, default=None, help="Path to .env file")
@click.version_option(version="0.1.0")
def cli(base_url: str, token: Optional[str], env_file: Optional[Path]):
    """
    Linguard CLI - Manage WireGuard VPN servers from the command line.

    This CLI provides a command-line interface to interact with the Linguard
    FastAPI backend for managing WireGuard servers, peers, and configurations.
    """
    global BASE_URL, AUTH_TOKEN

    # Load the env file first so its values can be picked up below
    if env_file and env_file.exists():
        load_dotenv(env_file)

    # Only override the module defaults when the option was explicitly passed;
    # otherwise fall back to the environment (env var or .env file).
    BASE_URL = base_url if base_url is not None else os.getenv("LINGUARD_API_URL", BASE_URL)
    AUTH_TOKEN = token if token is not None else os.getenv("LINGUARD_API_TOKEN", AUTH_TOKEN)
    
    if not HTTPX_AVAILABLE:
        click.echo("Error: httpx is required. Install with: pip install httpx")
        sys.exit(1)


@cli.group()
@click.pass_context
def auth(ctx):
    """Authentication commands."""
    pass


@auth.command()
@click.pass_context
def login(ctx):
    """
    Login to get authentication token.
    
    Requires username and password (or OIDC credentials if configured).
    Store the token in LINGUARD_API_TOKEN environment variable.
    """
    # Get credentials from stdin (for piped input) or prompt (for interactive)
    import sys
    
    if not sys.stdin.isatty():
        # Non-interactive: read from stdin
        lines = sys.stdin.readlines()
        if len(lines) >= 2:
            username = lines[0].strip()
            password = lines[1].strip()
            click.echo("Logging in to Linguard API...")
        else:
            click.echo("Error: Not enough input data", err=True)
            sys.exit(1)
    else:
        # Interactive: use click prompts
        click.echo("Logging in to Linguard API...")
        username = click.prompt("Username", hide_input=True)
        password = click.prompt("Password", hide_input=True)
    
    # Try basic auth first - use form-encoded data for OAuth2 compatibility
    try:
        # Send form data as a dict so httpx sets the correct
        # Content-Type (application/x-www-form-urlencoded)
        headers = {k: v for k, v in get_headers().items() if k != "Content-Type"}
        response = api_request("POST",
            f"{BASE_URL}{API_VERSION}/auth/token",
            data={"username": username, "password": password},
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            
            if token:
                click.echo("\n✓ Login successful!")
                click.echo(f"\nYour authentication token:")
                click.echo(f"  {token}")
                click.echo("\nSet this as your LINGUARD_API_TOKEN environment variable:")
                click.echo(f"  export LINGUARD_API_TOKEN='{token}'")
                
                # Offer to save to .env file (only when interactive)
                if sys.stdin.isatty():
                    save_to_env = click.confirm("Save token to .env file?")
                    if save_to_env:
                        env_path = Path(".env")
                        existing = env_path.read_text() if env_path.exists() else ""
                        # Keep every other line, replace any previous token
                        kept = [l for l in existing.splitlines() if not l.startswith("LINGUARD_API_TOKEN=")]
                        with open(env_path, "w") as f:
                            if kept:
                                f.write("\n".join(kept) + "\n")
                            f.write(f"LINGUARD_API_TOKEN={token}\n")
                        click.echo(f"✓ Token saved to {env_path}")
                
                click.echo("\nYou can now use the CLI without re-authenticating.")
                sys.exit(0)
            else:
                click.echo("Error: No token received from server", err=True)
                sys.exit(1)
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except httpx.HTTPError as e:
        click.echo(f"Error: HTTP request failed - {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@auth.command()
@click.pass_context
def status(ctx):
    """Check authentication status."""
    if not AUTH_TOKEN:
        click.echo("Error: No authentication token set. Run 'linguard auth login' first.")
        sys.exit(1)
    
    try:
        response = api_request("GET",
            f"{BASE_URL}{API_VERSION}/auth/profile",
            headers=get_headers(),
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            click.echo("✓ Authentication successful!")
            click.echo(f"  User: {data.get('username')}")
            click.echo(f"  Email: {data.get('email')}")
            click.echo(f"  Role: {data.get('role')}")
        else:
            click.echo(f"✗ Authentication failed (HTTP {response.status_code})", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@auth.command()
def logout():
    """Clear authentication token."""
    global AUTH_TOKEN
    click.echo("Clearing authentication token...")
    AUTH_TOKEN = None
    click.echo("✓ Token cleared. You will need to login again.")


@cli.group()
@click.pass_context
def servers(ctx):
    """Server management commands."""
    pass


@servers.command("start")
@click.argument("server_id")
@click.pass_context
def start_server(ctx, server_id: int):
    """Start a WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/servers/{server_id}/start",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✓ Server {server_id} started successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Status: {data.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("stop")
@click.argument("server_id")
@click.pass_context
def stop_server(ctx, server_id: int):
    """Stop a WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/servers/{server_id}/stop",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✓ Server {server_id} stopped successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Status: {data.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("reload")
@click.argument("server_id")
@click.pass_context
def reload_server(ctx, server_id: int):
    """Reload a WireGuard server configuration."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/servers/{server_id}/reload",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo(f"✓ Server {server_id} reloaded successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Status: {data.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("list")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
def list_servers(ctx, json: bool):
    """List all WireGuard servers."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/servers",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                servers = extract_items(data)
                if servers:
                    click.echo(f"Found {len(servers)} server(s):\n")
                    # Create table
                    headers = ["Name", "Interface", "Port", "Status"]
                    rows = []
                    for server in servers:
                        rows.append([
                            server.get('name', 'Unknown'),
                            server.get('interface', 'N/A'),
                            str(server.get('listen_port', 'N/A')),
                            server.get('status', 'unknown'),
                        ])
                    print_table(headers, rows)
                else:
                    click.echo("No servers found.")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("create")
@click.pass_context
@click.option("--name", default=None, help="Server name")
@click.option("--port", default=None, type=int, help="Listen port (1-65535)")
@click.option("--endpoint", default=None, help="Server endpoint (hostname or IP)")
@click.option("--ipv4", default=None, help="IPv4 address (e.g., 10.0.0.1/24)")
@click.option("--ipv6", default=None, help="IPv6 address (e.g., fd00::1/64)")
@click.option("--dns-primary", default=None, help="Primary DNS server")
@click.option("--dns-secondary", default=None, help="Secondary DNS server")
@click.option("--autostart", is_flag=True, help="Autostart server on boot")
@click.option("--description", default=None, help="Server description")
@click.option("--suggest-ip", "-s", is_flag=True, help="Suggest IP addresses")
@click.option("--suggest-dns", "-d", is_flag=True, help="Suggest DNS servers")
@click.option("--suggest-port", "-p", is_flag=True, help="Suggest ports")
def create_server(
    ctx,
    name: str,
    port: int,
    endpoint: str,
    ipv4: Optional[str],
    ipv6: Optional[str],
    dns_primary: Optional[str],
    dns_secondary: Optional[str],
    autostart: bool,
    description: Optional[str],
    suggest_ip: bool,
    suggest_dns: bool,
    suggest_port: bool,
):
    """Create a new WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    # Handle suggestions
    if suggest_ip or suggest_dns or suggest_port:
        from linguard_cli.completers import IPCompleter
        if suggest_ip:
            click.echo("Suggested IP addresses:")
            for i, ip in enumerate(IPCompleter.suggest_ips("10.0.0", min_length=1)[:10], 1):
                click.echo(f"  {i}. {ip}")
        if suggest_dns:
            click.echo("Suggested DNS servers:")
            for provider, servers in IPCompleter.suggest_all_dns():
                click.echo(f"  {provider}: {', '.join(servers[:2])}")
        if suggest_port:
            click.echo("Suggested ports: " + ", ".join(str(p) for p in IPCompleter.suggest_ports()))
        return

    # Required options are validated here (not via required=True) so the
    # suggestion flags (-s/-d/-p) can run without them
    if not name or not port or not endpoint:
        raise click.UsageError(
            "Missing options: --name, --port and --endpoint are required "
            "(unless using the -s/-d/-p suggestion flags)."
        )

    # Generate keypair
    try:
        click.echo("Generating WireGuard keypair...")
        gen_keypair_response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/utils/generate-keypair",
            headers=get_headers(),
            timeout=10.0
        )
        
        if gen_keypair_response.status_code != 200:
            click.echo("Error: Failed to generate keypair", err=True)
            sys.exit(1)
        
        keypair = gen_keypair_response.json()
        public_key = keypair.get("public_key")
        private_key = keypair.get("private_key")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    # Prepare server data
    server_data = {
        "name": name,
        "listen_port": port,
        "endpoint": endpoint,
        "public_key": public_key,
        "private_key": private_key,
        "autostart": autostart,
    }
    
    if ipv4:
        server_data["ipv4_address"] = ipv4
    if ipv6:
        server_data["ipv6_address"] = ipv6
    if dns_primary:
        server_data["dns_primary"] = dns_primary
    if dns_secondary:
        server_data["dns_secondary"] = dns_secondary
    if description:
        server_data["description"] = description
    
    try:
        click.echo(f"Creating server '{name}'...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/servers",
            json=server_data,
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo(f"✓ Server created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Interface: {data.get('interface')}")
            click.echo(f"  Port: {data.get('listen_port')}")
            click.echo(f"  Status: {data.get('status')}")
            
            # Start server if requested
            if autostart:
                click.echo("\nStarting server...")
                start_response = api_request("POST", 
                    f"{BASE_URL}{API_VERSION}/servers/{data['id']}/start",
                    headers=get_headers(),
                    timeout=30.0
                )
                
                if start_response.status_code == 200:
                    click.echo("✓ Server started successfully!")
                else:
                    click.echo("✗ Failed to start server", err=True)
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("delete")
@click.argument("server_id")
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_server(ctx, server_id: int, yes: bool):
    """Delete a WireGuard server."""
    if not check_api_health():
        sys.exit(1)

    if not yes and not click.confirm(f"Are you sure you want to delete server {server_id}? This action cannot be undone."):
        click.echo("Delete cancelled.")
        return
    
    try:
        response = api_request("DELETE", 
            f"{BASE_URL}{API_VERSION}/servers/{server_id}",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 204:
            click.echo(f"✓ Server {server_id} deleted successfully!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def peers(ctx):
    """Peer management commands."""
    pass


@peers.command("list")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
def list_peers(ctx, json: bool):
    """List all peers across all servers."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/peers",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                peers = extract_items(data)
                if peers:
                    click.echo(f"Found {len(peers)} peer(s):\n")
                    # Create table
                    headers = ["Name", "Server", "IPv4", "Allowed IPs", "Enabled", "RX", "TX"]
                    rows = []
                    for peer in peers:
                        rows.append([
                            peer.get('name', 'Unknown'),
                            str(peer.get('server_id', 'N/A')),
                            peer.get('ipv4_address', 'N/A'),
                            peer.get('allowed_ips', 'N/A'),
                            "✓" if peer.get('enabled') else "✗",
                            format_bytes(peer.get('rx_bytes', 0)),
                            format_bytes(peer.get('tx_bytes', 0)),
                        ])
                    print_table(headers, rows)
                else:
                    click.echo("No peers found.")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@peers.command("create")
@click.pass_context
@click.argument("server_id")
@click.option("--name", default=None, help="Peer name")
@click.option("--endpoint", default=None, help="Peer endpoint (public IP/hostname)")
@click.option("--allowed-ips", default=None, help="Allowed IPs (e.g., 10.0.0.0/24)")
@click.option("--ipv4", default=None, help="Peer IPv4 address (e.g., 10.11.0.2/32)")
@click.option("--ipv6", default=None, help="IPv6 address")
@click.option("--port", default=51820, help="Peer port")
@click.option("--dns-primary", default=None, help="Primary DNS")
@click.option("--dns-secondary", default=None, help="Secondary DNS")
@click.option("--preshared-key", default=None, help="Pre-shared key (optional)")
@click.option("--persistent-keepalive", default=60, type=int, help="Persistent keepalive (seconds)")
@click.option("--suggest-ip", "-s", is_flag=True, help="Suggest IP addresses")
@click.option("--suggest-range", "-r", is_flag=True, help="Suggest IP ranges")
def create_peer(ctx,
    server_id: int,
    name: str,
    endpoint: str,
    allowed_ips: Optional[str],
    ipv4: Optional[str],
    ipv6: Optional[str],
    port: int,
    dns_primary: Optional[str],
    dns_secondary: Optional[str],
    preshared_key: Optional[str],
    persistent_keepalive: int,
    suggest_ip: bool,
    suggest_range: bool,
):
    """Create a new peer for a server."""
    if not check_api_health():
        sys.exit(1)
    
    # Handle IP suggestions
    if suggest_ip or suggest_range:
        from linguard_cli.completers import IPCompleter
        if suggest_ip:
            click.echo("Suggested IP addresses:")
            for i, ip in enumerate(IPCompleter.suggest_ips("10.0.0", min_length=1)[:10], 1):
                click.echo(f"  {i}. {ip}")
        if suggest_range:
            click.echo("Common subnet ranges:")
            for subnet, desc in IPCompleter.suggest_common_subnets()[:6]:
                click.echo(f"  {subnet:<20} - {desc}")
        return

    # Required options are validated here (not via required=True) so the
    # suggestion flags (-s/-r) can run without them
    if not name or not endpoint:
        raise click.UsageError(
            "Missing options: --name and --endpoint are required "
            "(unless using the -s/-r suggestion flags)."
        )

    try:
        # Validate the server exists
        click.echo(f"Getting server {server_id} configuration...")
        server_response = api_request("GET",
            f"{BASE_URL}{API_VERSION}/servers/{server_id}",
            headers=get_headers(),
            timeout=10.0
        )

        if server_response.status_code != 200:
            click.echo("Error: Server not found", err=True)
            sys.exit(1)

        # Fetch auto-filled defaults (next available IP, fresh keypair, DNS...)
        defaults_response = api_request("GET",
            f"{BASE_URL}{API_VERSION}/peers/defaults/{server_id}",
            headers=get_headers(),
            timeout=10.0
        )
        defaults = defaults_response.json() if defaults_response.status_code == 200 else {}

        peer_data = {
            "server_id": server_id,
            "name": name,
            "endpoint": endpoint,
            "port": port,
            "persistent_keepalive": persistent_keepalive,
            "public_key": defaults.get('public_key'),
            "private_key": defaults.get('private_key'),
        }

        # Peer address: explicit option wins, otherwise the suggested one
        if ipv4:
            peer_data["ipv4_address"] = ipv4
        elif defaults.get('ipv4_address'):
            peer_data["ipv4_address"] = defaults['ipv4_address']
        if ipv6:
            peer_data["ipv6_address"] = ipv6
        elif defaults.get('ipv6_address'):
            peer_data["ipv6_address"] = defaults['ipv6_address']

        # allowed_ips: only when explicitly provided (the backend applies
        # its own defaults — full-tunnel — when omitted)
        if allowed_ips:
            peer_data["allowed_ips"] = allowed_ips

        if dns_primary:
            peer_data["dns_primary"] = dns_primary
        elif defaults.get('dns_primary'):
            peer_data["dns_primary"] = defaults['dns_primary']
        if dns_secondary:
            peer_data["dns_secondary"] = dns_secondary
        elif defaults.get('dns_secondary'):
            peer_data["dns_secondary"] = defaults['dns_secondary']

        if preshared_key:
            peer_data["preshared_key"] = preshared_key
        elif defaults.get('preshared_key'):
            peer_data["preshared_key"] = defaults['preshared_key']
        
        click.echo(f"Creating peer '{name}' on server {server_id}...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/peers",
            json=peer_data,
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo(f"✓ Peer created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  IPv4: {data.get('ipv4_address') or 'N/A'}")
            click.echo(f"  Allowed IPs: {data.get('allowed_ips') or 'N/A'}")
            click.echo(f"  Public key: {data.get('public_key')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@peers.command("delete")
@click.argument("peer_id")
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_peer(ctx, peer_id: int, yes: bool):
    """Delete a peer."""
    if not check_api_health():
        sys.exit(1)

    if not yes and not click.confirm(f"Are you sure you want to delete peer {peer_id}?"):
        click.echo("Delete cancelled.")
        return
    
    try:
        response = api_request("DELETE", 
            f"{BASE_URL}{API_VERSION}/peers/{peer_id}",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 204:
            click.echo(f"✓ Peer {peer_id} deleted successfully!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def backups(ctx):
    """Backup and restore commands."""
    pass


@backups.command("list")
@click.pass_context
def list_backups(ctx):
    """List all backups."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/backups",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            backups = extract_items(data)
            if backups:
                click.echo(f"Found {len(backups)} backup(s):\n")
                # Create table
                headers = ["Name", "Created", "Size"]
                rows = []
                for backup in backups:
                    rows.append([
                        backup.get('filename', 'N/A'),
                        backup.get('created_at', 'N/A'),
                        f"{backup.get('file_size', 0) / 1024:.1f} KB",
                    ])
                print_table(headers, rows)
            else:
                click.echo("No backups found.")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@backups.command("create")
@click.pass_context
@click.option("--name", default=None, help="Backup name")
def create_backup(ctx, name: Optional[str]):
    """Create a new backup."""
    if not check_api_health():
        sys.exit(1)
    
    backup_data = {}
    if name:
        backup_data["name"] = name
    
    try:
        click.echo("Creating backup...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/backups",
            json=backup_data,
            headers=get_headers(),
            timeout=60.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo("✓ Backup created successfully!")
            click.echo(f"  Filename: {data.get('filename') or 'N/A'}")
            click.echo(f"  ID: {data.get('id')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def traffic_triggers(ctx):
    """Traffic trigger management commands."""
    pass


@traffic_triggers.command("list")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
def list_triggers(ctx, json: bool):
    """List all traffic triggers."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/traffic-triggers",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                click.echo(f"Found {len(extract_items(data))} trigger(s):\n")
                for trigger in extract_items(data):
                    name = trigger.get('name', 'Unknown')
                    enabled = "✓" if trigger.get('enabled') else "✗"
                    scope = trigger.get('scope', 'Unknown')
                    click.echo(f"  {enabled} {name}")
                    click.echo(f"     Scope: {scope} | {trigger.get('direction', '?')} > {format_bytes(trigger.get('threshold_bytes', 0))} / {trigger.get('window', '?')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@traffic_triggers.command("create")
@click.pass_context
@click.option("--name", required=True, help="Trigger name")
@click.option("--scope", required=True, type=click.Choice(['peer', 'server', 'global']), help="Scope (peer/server/global)")
@click.option("--peer-id", default=None, help="Peer ID (for peer scope)")
@click.option("--server-id", default=None, help="Server ID (for server scope)")
@click.option("--direction", required=True, type=click.Choice(['rx', 'tx', 'combined']), help="Traffic direction")
@click.option("--threshold-bytes", required=True, type=int, help="Threshold in bytes")
@click.option("--window", required=True, type=click.Choice(['last_hour', 'last_24_hours', 'last_7_days', 'last_30_days']), help="Time window")
@click.option("--cooldown-minutes", default=5, type=int, help="Cooldown in minutes")
@click.option("--integration-ids", default=None, help="Comma-separated integration IDs")
def create_trigger(ctx,
    name: str,
    scope: str,
    peer_id: Optional[int],
    server_id: Optional[int],
    direction: str,
    threshold_bytes: int,
    window: str,
    cooldown_minutes: int,
    integration_ids: Optional[str]
):
    """Create a new traffic trigger."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        trigger_data = {
            "name": name,
            "scope": scope,
            "direction": direction,
            "threshold_bytes": threshold_bytes,
            "window": window,
            "cooldown_minutes": cooldown_minutes,
            "enabled": False,
        }
        
        if peer_id is not None:
            trigger_data["peer_id"] = peer_id
        elif server_id is not None:
            trigger_data["server_id"] = server_id
        
        if integration_ids:
            trigger_data["integration_ids"] = [int(x.strip()) for x in integration_ids.split(",")]
        
        click.echo(f"Creating traffic trigger '{name}'...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/traffic-triggers",
            json=trigger_data,
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo("✓ Traffic trigger created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Scope: {data.get('scope')} | Direction: {data.get('direction')}")
            click.echo(f"  Enabled: {'yes' if data.get('enabled') else 'no'}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@traffic_triggers.command("delete")
@click.argument("trigger_id")
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_trigger(ctx, trigger_id: int, yes: bool):
    """Delete a traffic trigger."""
    if not check_api_health():
        sys.exit(1)

    if not yes and not click.confirm(f"Are you sure you want to delete trigger {trigger_id}?"):
        click.echo("Delete cancelled.")
        return
    
    try:
        response = api_request("DELETE", 
            f"{BASE_URL}{API_VERSION}/traffic-triggers/{trigger_id}",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 204:
            click.echo(f"✓ Trigger {trigger_id} deleted successfully!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@traffic_triggers.command("test")
@click.argument("trigger_id")
@click.pass_context
def test_trigger(ctx, trigger_id: int):
    """Test a traffic trigger."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        click.echo(f"Testing trigger {trigger_id}...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/traffic-triggers/{trigger_id}/test",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo("✓ Trigger test completed!")
            click.echo(f"  Would trigger: {'yes' if data.get('would_trigger') else 'no'}")
            click.echo(f"  Current traffic: {format_bytes(data.get('current_bytes', 0))} / threshold {format_bytes(data.get('threshold_bytes', 0))}")
            reason = data.get('reason')
            if reason:
                click.echo(f"  Reason: {reason}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def integrations(ctx):
    """Integration management commands."""
    pass


@integrations.command("list")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
def list_integrations(ctx, json: bool):
    """List all integrations."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/integrations",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                click.echo(f"Found {len(extract_items(data))} integration(s):\n")
                for integration in extract_items(data):
                    name = integration.get('name', 'Unknown')
                    type_ = integration.get('type', 'Unknown')
                    enabled = "✓" if integration.get('enabled') else "✗"
                    click.echo(f"  {enabled} {name}")
                    click.echo(f"     Type: {type_} | Events: {len(integration.get('events_subscribed', []))}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@integrations.command("create")
@click.pass_context
@click.option("--name", required=True, help="Integration name")
@click.option("--type", "type_", required=True, type=click.Choice(['webhook', 'notification', 'email']), help="Integration type")
@click.option("--url", default=None, help="Webhook URL")
@click.option("--events", default=None, help="Comma-separated event types")
def create_integration(ctx, name: str, type_: str, url: Optional[str], events: Optional[str]):
    """Create a new integration."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        integration_data = {
            "name": name,
            "type": type_,
            "enabled": True,
            "config": {},
        }
        
        if url:
            integration_data["config"]["url"] = url
        
        if events:
            integration_data["events_subscribed"] = [e.strip() for e in events.split(",")]
        
        click.echo(f"Creating integration '{name}'...")
        response = api_request("POST", 
            f"{BASE_URL}{API_VERSION}/integrations",
            json=integration_data,
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo("✓ Integration created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Type: {data.get('type')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@integrations.command("delete")
@click.argument("integration_id")
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_integration(ctx, integration_id: int, yes: bool):
    """Delete an integration."""
    if not check_api_health():
        sys.exit(1)

    if not yes and not click.confirm(f"Are you sure you want to delete integration {integration_id}?"):
        click.echo("Delete cancelled.")
        return
    
    try:
        response = api_request("DELETE", 
            f"{BASE_URL}{API_VERSION}/integrations/{integration_id}",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 204:
            click.echo(f"✓ Integration {integration_id} deleted successfully!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def notifications(ctx):
    """Notification management commands."""
    pass


@notifications.command("list")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
def list_notifications(ctx, json: bool):
    """List all notifications."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/notifications",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                unread = len([n for n in extract_items(data) if not n.get('read')])
                click.echo(f"Found {len(extract_items(data))} notification(s) ({unread} unread)\n")
                for notif in extract_items(data):
                    date = notif.get('created_at', 'Unknown')
                    read_status = "✓" if notif.get('read') else "✗"
                    click.echo(f"  {read_status} [{date}] {notif.get('title', 'No title')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@notifications.command("mark-all-read")
@click.pass_context
def mark_all_read(ctx):
    """Mark all notifications as read."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("PUT", 
            f"{BASE_URL}{API_VERSION}/notifications/read/all",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            click.echo("✓ All notifications marked as read!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@notifications.command("clear-all")
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def clear_all(ctx, yes: bool):
    """Clear all notifications."""
    if not check_api_health():
        sys.exit(1)

    if not yes and not click.confirm("Are you sure you want to clear all notifications?"):
        click.echo("Clear cancelled.")
        return
    
    try:
        response = api_request("DELETE", 
            f"{BASE_URL}{API_VERSION}/notifications/all",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            click.echo("✓ All notifications cleared!")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def metrics(ctx):
    """Metrics and monitoring commands."""
    pass


@metrics.command("traffic")
@click.pass_context
@click.option("--scope", required=True, type=click.Choice(['peer', 'server', 'global']), help="Metrics scope")
@click.option("--server-id", default=None, help="Server ID (for server scope)")
@click.option("--peer-id", default=None, help="Peer ID (for peer scope)")
@click.option("--json", is_flag=True, help="Output in JSON format")
def get_traffic_metrics(ctx, scope: str, server_id: Optional[int], peer_id: Optional[int], json: bool):
    """Get traffic metrics."""
    if not check_api_health():
        sys.exit(1)

    try:
        # Map the scope to the real backend endpoints
        if scope == 'global':
            url = f"{BASE_URL}{API_VERSION}/metrics/dashboard"
        elif scope == 'server':
            if server_id:
                url = f"{BASE_URL}{API_VERSION}/metrics/server/{server_id}"
            else:
                url = f"{BASE_URL}{API_VERSION}/metrics/servers/aggregate"
        else:  # peer
            if peer_id:
                url = f"{BASE_URL}{API_VERSION}/metrics/peer/{peer_id}"
            else:
                url = f"{BASE_URL}{API_VERSION}/metrics/peers/aggregate"

        response = api_request("GET",
            url,
            headers=get_headers(),
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()

            if json:
                click.echo(json.dumps(data, indent=2))
                return

            click.echo("Traffic Metrics:")
            click.echo(f"  Scope: {scope}")

            if scope == 'global':
                servers_totals = data.get('servers', {}).get('current_totals', {})
                peers_totals = data.get('peers', {}).get('current_totals', {})
                total_rx = servers_totals.get('total_rx_bytes', 0) + peers_totals.get('total_rx_bytes', 0)
                total_tx = servers_totals.get('total_tx_bytes', 0) + peers_totals.get('total_tx_bytes', 0)
                click.echo(f"  Total RX: {format_bytes(total_rx)}")
                click.echo(f"  Total TX: {format_bytes(total_tx)}")
                for server in data.get('servers', {}).get('top_servers', [])[:5]:
                    click.echo(f"  Top Server: {server.get('name', 'Unknown')}")
                    click.echo(f"    RX: {format_bytes(server.get('rx_bytes', 0))} | TX: {format_bytes(server.get('tx_bytes', 0))}")
                for peer in data.get('peers', {}).get('top_peers', [])[:5]:
                    click.echo(f"  Top Peer: {peer.get('name', 'Unknown')}")
                    click.echo(f"    RX: {format_bytes(peer.get('rx_bytes', 0))} | TX: {format_bytes(peer.get('tx_bytes', 0))}")
            elif scope == 'server':
                if server_id:
                    server = data.get('server', {})
                    click.echo(f"  Server: {server.get('name', 'Unknown')}")
                    click.echo(f"    RX: {format_bytes(server.get('current_rx_bytes', 0))} | TX: {format_bytes(server.get('current_tx_bytes', 0))}")
                else:
                    totals = data.get('current_totals', {})
                    click.echo(f"  Total RX: {format_bytes(totals.get('total_rx_bytes', 0))}")
                    click.echo(f"  Total TX: {format_bytes(totals.get('total_tx_bytes', 0))}")
                    for server in data.get('servers', []):
                        click.echo(f"    - {server.get('name', 'Unknown')}: RX {format_bytes(server.get('rx_bytes', 0))} | TX {format_bytes(server.get('tx_bytes', 0))}")
            else:  # peer
                if peer_id:
                    peer = data.get('peer', {})
                    click.echo(f"  Peer: {peer.get('name', 'Unknown')}")
                    click.echo(f"    RX: {format_bytes(peer.get('current_rx_bytes', 0))} | TX: {format_bytes(peer.get('current_tx_bytes', 0))}")
                else:
                    totals = data.get('current_totals', {})
                    click.echo(f"  Total RX: {format_bytes(totals.get('total_rx_bytes', 0))}")
                    click.echo(f"  Total TX: {format_bytes(totals.get('total_tx_bytes', 0))}")
                    for peer in data.get('peers', []):
                        click.echo(f"    - {peer.get('name', 'Unknown')}: RX {format_bytes(peer.get('rx_bytes', 0))} | TX {format_bytes(peer.get('tx_bytes', 0))}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable format."""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"


def print_table(headers: list, rows: list):
    """Print a formatted table from headers and rows of strings."""
    if not rows:
        return
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Build header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * w for w in widths)
    
    # Build body
    body_lines = [header_line, separator]
    for row in rows:
        body_lines.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    
    click.echo("\n".join(body_lines))
    click.echo()


@cli.group("status")
@click.pass_context
def status_command(ctx):
    """Status and health commands."""
    pass


@status_command.command("system")
@click.pass_context
def system_status(ctx):
    """Show system information."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}{API_VERSION}/system",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            app_info = data.get('app', {})
            host = data.get('host', {})
            uptime_seconds = app_info.get('uptime_seconds', 0)
            hours, rem = divmod(uptime_seconds, 3600)
            minutes = rem // 60
            uptime_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            rows = [
                ["App", app_info.get('name', 'N/A')],
                ["Version", app_info.get('version', 'N/A')],
                ["Uptime", uptime_str],
                ["Python", (app_info.get('python_version', '') or 'N/A').split()[0]],
                ["Hostname", host.get('hostname', 'N/A')],
                ["OS", f"{host.get('os', 'N/A')} {host.get('os_release', '')}".strip()],
                ["CPU cores", str(host.get('cpu_count', 'N/A'))],
                ["CPU usage", f"{host.get('cpu_percent', 0)}%"],
                ["RAM", f"{format_bytes(host.get('ram_used_bytes', 0))} / {format_bytes(host.get('ram_total_bytes', 0))} ({host.get('ram_percent', 0)}%)"],
            ]
            print_table(["Component", "Value"], rows)
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@status_command.command("health")
@click.pass_context
def health_check(ctx):
    """Run health check on the system."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = api_request("GET", 
            f"{BASE_URL}/health",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            
            # Print status with emoji
            emoji = "✓" if status == 'healthy' else "✗"
            color = "green" if status == 'healthy' else "red"
            click.echo(f"\n{click.style(emoji, fg=color)} System Health Check")
            click.echo(f"  Overall Status: {click.style(status, fg='green' if status == 'healthy' else 'red')}")
            
            # Print detailed checks
            checks = data.get('checks', {})
            click.echo("\nDetailed Checks:")
            for check_name, check_data in checks.items():
                check_status = check_data.get('status', 'unknown')
                check_emoji = "✓" if check_status == 'healthy' else "✗"
                click.echo(f"  {check_emoji} {check_name}: {check_status}")
                
                if 'message' in check_data:
                    click.echo(f"     - {check_data['message']}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group("completers")
@click.pass_context
def completers(ctx):
    """Intelligent autocomplete suggestions."""
    pass


@completers.command("ip")
@click.option("--count", "--min-length", "min_length", default=10, help="Number of suggestions")
@click.option("--prefix", default=None, help="IP prefix to match")
def suggest_ip(min_length: int, prefix: Optional[str]):
    """Suggest IP addresses."""
    from linguard_cli.completers import IPCompleter
    
    ips = IPCompleter.suggest_ips(prefix=prefix, min_length=min_length)
    
    click.echo("📍 IP Address Suggestions:")
    click.echo("-" * 60)
    for i, ip in enumerate(ips, 1):
        click.echo(f"   {i}. {ip}")


@completers.command("subnet")
@click.option("--class", "cls", type=click.Choice(['A', 'B', 'C', 'All']), default='All', help="Subnet class")
def suggest_subnet(cls: str):
    """Suggest common subnet ranges."""
    from linguard_cli.completers import IPCompleter
    
    if cls == 'A':
        subnets = IPCompleter.suggest_class_a()
    elif cls == 'B':
        subnets = IPCompleter.suggest_class_b()
    elif cls == 'C':
        subnets = IPCompleter.suggest_class_c()
    else:
        subnets = IPCompleter.suggest_common_subnets()
    
    click.echo("📟 Common Subnet Ranges:")
    click.echo("-" * 60)
    for subnet, hosts in subnets:
        desc = IPCompleter._get_subnet_description(subnet)
        click.echo(f"   {subnet:30} - {desc}")


@completers.command("dns")
@click.option("--provider", "provider", type=click.Choice(['cloudflare', 'google', 'quad9']), help="DNS provider")
def suggest_dns(provider: Optional[str]):
    """Suggest public DNS servers."""
    from linguard_cli.completers import IPCompleter
    
    if provider:
        dns_servers = IPCompleter.suggest_dns(provider=provider)
    else:
        dns_servers = IPCompleter.suggest_all_dns()
    
    click.echo("🌐 DNS Server Suggestions:")
    click.echo("-" * 60)
    for provider_name, servers in dns_servers:
        click.echo(f"\n   {provider_name.capitalize()} DNS:")
        for dns in servers:
            click.echo(f"      {dns}")


@completers.command("port")
@click.option("--range", "port_range", default=None, help="Port range (e.g., 51820-65535)")
def suggest_port(port_range: Optional[str]):
    """Suggest common WireGuard ports."""
    from linguard_cli.completers import IPCompleter
    
    ports = IPCompleter.suggest_ports()
    
    click.echo("🔌 Common WireGuard Ports:")
    click.echo("-" * 60)
    for port in ports:
        click.echo(f"   {port}")


@completers.command("peer")
@click.option("--server-port", default=51820, help="Server port for peer suggestions")
def suggest_peer(server_port: int):
    """Suggest peer names."""
    from linguard_cli.completers import IPCompleter
    
    peer_names = IPCompleter.suggest_peer_names()
    
    click.echo("👥 Suggested Peer Names:")
    click.echo("-" * 60)
    for i, name in enumerate(peer_names, 1):
        click.echo(f"   {i}. {name}")


if __name__ == "__main__":
    cli()
