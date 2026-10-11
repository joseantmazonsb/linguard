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
    import requests
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
        response = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        return response.status_code == 200
    except Exception as e:
        click.echo(f"Error: Cannot connect to API at {BASE_URL} - {e}", err=True)
        return False


@click.group()
@click.option("--base-url", default=BASE_URL, help=f"API base URL (default: {BASE_URL})")
@click.option("--token", default=None, help="API authentication token")
@click.option("--env-file", type=Path, default=None, help="Path to .env file")
@click.version_option(version="0.1.0")
def cli(base_url: str, token: Optional[str], env_file: Optional[Path]):
    """
    Linguard CLI - Manage WireGuard VPN servers from the command line.
    
    This CLI provides a command-line interface to interact with the Linguard
    FastAPI backend for managing WireGuard servers, peers, and configurations.
    """
    global BASE_URL, AUTH_TOKEN
    
    BASE_URL = base_url
    AUTH_TOKEN = token
    
    if env_file and env_file.exists():
        load_dotenv(env_file)
    
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
    click.echo("Logging in to Linguard API...")
    
    # Get credentials from user
    username = click.prompt("Username", hide_input=True)
    password = click.prompt("Password", hide_input=True)
    
    # Try basic auth first
    try:
        response = httpx.post(
            f"{BASE_URL}{API_VERSION}/auth/login",
            json={"username": username, "password": password},
            headers=get_headers(),
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
                
                # Offer to save to .env file
                save_to_env = click.confirm("Save token to .env file?")
                if save_to_env:
                    env_path = Path(".env")
                    with open(env_path, "w") as f:
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
        response = httpx.get(
            f"{BASE_URL}{API_VERSION}/auth/me",
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
            click.echo("✗ Authentication failed or expired", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@auth.command()
def logout():
    """Clear authentication token."""
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
def start_server(server_id: int):
    """Start a WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = httpx.post(
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
def stop_server(server_id: int):
    """Stop a WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = httpx.post(
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
def reload_server(server_id: int):
    """Reload a WireGuard server configuration."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = httpx.post(
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
        response = httpx.get(
            f"{BASE_URL}{API_VERSION}/servers",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                click.echo(f"Found {len(data.get('items', []))} server(s):\n")
                for server in data.get('items', []):
                    status_emoji = "🟢" if server.get('status') == 'running' else "🔴"
                    click.echo(f"  {status_emoji} {server.get('name')} ({server.get('interface')})")
                    click.echo(f"     Port: {server.get('listen_port')} | Status: {server.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@servers.command("create")
@click.pass_context
@click.option("--name", required=True, help="Server name")
@click.option("--port", required=True, type=int, help="Listen port (1-65535)")
@click.option("--endpoint", required=True, help="Server endpoint (hostname or IP)")
@click.option("--ipv4", default=None, help="IPv4 address (e.g., 10.0.0.1/24)")
@click.option("--ipv6", default=None, help="IPv6 address (e.g., fd00::1/64)")
@click.option("--dns-primary", default=None, help="Primary DNS server")
@click.option("--dns-secondary", default=None, help="Secondary DNS server")
@click.option("--autostart", is_flag=True, help="Autostart server on boot")
@click.option("--description", default=None, help="Server description")
def create_server(
    name: str,
    port: int,
    endpoint: str,
    ipv4: Optional[str],
    ipv6: Optional[str],
    dns_primary: Optional[str],
    dns_secondary: Optional[str],
    autostart: bool,
    description: Optional[str]
):
    """Create a new WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    # Generate keypair
    try:
        click.echo("Generating WireGuard keypair...")
        gen_keypair_response = httpx.get(
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
        response = httpx.post(
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
                start_response = httpx.post(
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
def delete_server(server_id: int):
    """Delete a WireGuard server."""
    if not check_api_health():
        sys.exit(1)
    
    confirmation = click.confirm(f"Are you sure you want to delete server {server_id}? This action cannot be undone.")
    
    if not confirmation:
        click.echo("Delete cancelled.")
        return
    
    try:
        response = httpx.delete(
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
        response = httpx.get(
            f"{BASE_URL}{API_VERSION}/peers",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if json:
                click.echo(json.dumps(data, indent=2))
            else:
                click.echo(f"Found {len(data.get('items', []))} peer(s):\n")
                for peer in data.get('items', []):
                    name = peer.get('name', 'Unknown')
                    enabled = "✓" if peer.get('enabled') else "✗"
                    click.echo(f"  {enabled} {name} (Server: {peer.get('server_name')})")
                    click.echo(f"     Enabled: {enabled} | Status: {peer.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@peers.command("create")
@click.pass_context
@click.argument("server_id")
@click.option("--name", required=True, help="Peer name")
@click.option("--endpoint", required=True, help="Peer endpoint (public IP/hostname)")
@click.option("--allowed-ips", default=None, help="Allowed IPs (e.g., 10.0.0.0/24)")
@click.option("--ipv6", default=None, help="IPv6 address")
@click.option("--port", default=51820, help="Peer port")
@click.option("--dns-primary", default=None, help="Primary DNS")
@click.option("--dns-secondary", default=None, help="Secondary DNS")
@click.option("--preshared-key", default=None, help="Pre-shared key (optional)")
@click.option("--persistent-keepalive", default=60, type=int, help="Persistent keepalive (seconds)")
def create_peer(
    server_id: int,
    name: str,
    endpoint: str,
    allowed_ips: Optional[str],
    ipv6: Optional[str],
    port: int,
    dns_primary: Optional[str],
    dns_secondary: Optional[str],
    preshared_key: Optional[str],
    persistent_keepalive: int
):
    """Create a new peer for a server."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        # Get server config to generate suggested IP
        click.echo(f"Getting server {server_id} configuration...")
        server_response = httpx.get(
            f"{BASE_URL}{API_VERSION}/servers/{server_id}",
            headers=get_headers(),
            timeout=10.0
        )
        
        if server_response.status_code != 200:
            click.echo("Error: Server not found", err=True)
            sys.exit(1)
        
        server_data = server_response.json()
        ipv4_suggested = server_data.get('ipv4_suggested')
        ipv6_suggested = server_data.get('ipv6_suggested')
        
        peer_data = {
            "name": name,
            "endpoint": endpoint,
            "port": port,
            "persistent_keepalive": persistent_keepalive,
        }
        
        if ipv4_suggested and not ipv6:
            peer_data["ipv4_address"] = ipv4_suggested
        elif ipv6_suggested and not ipv6:
            peer_data["ipv6_address"] = ipv6_suggested
        elif ipv6:
            peer_data["ipv6_address"] = ipv6
        elif allowed_ips:
            peer_data["allowed_ips"] = allowed_ips
            
        if dns_primary:
            peer_data["dns_primary"] = dns_primary
        if dns_secondary:
            peer_data["dns_secondary"] = dns_secondary
        if preshared_key:
            peer_data["preshared_key"] = preshared_key
        
        click.echo(f"Creating peer '{name}' on server {server_id}...")
        response = httpx.post(
            f"{BASE_URL}{API_VERSION}/peers",
            json=peer_data,
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo(f"✓ Peer created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  Endpoint: {data.get('endpoint')}")
            click.echo(f"  Status: {data.get('status')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@peers.command("delete")
@click.argument("peer_id")
@click.pass_context
def delete_peer(peer_id: int):
    """Delete a peer."""
    if not check_api_health():
        sys.exit(1)
    
    confirmation = click.confirm(f"Are you sure you want to delete peer {peer_id}?")
    
    if not confirmation:
        click.echo("Delete cancelled.")
        return
    
    try:
        response = httpx.delete(
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
        response = httpx.get(
            f"{BASE_URL}{API_VERSION}/backups",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo(f"Found {len(data.get('items', []))} backup(s):\n")
            
            for backup in data.get('items', []):
                created = backup.get('created_at', 'Unknown')
                size = backup.get('size', 'Unknown')
                click.echo(f"  - {backup.get('name')}")
                click.echo(f"    Created: {created} | Size: {size}")
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
        response = httpx.post(
            f"{BASE_URL}{API_VERSION}/backups",
            json=backup_data,
            headers=get_headers(),
            timeout=60.0
        )
        
        if response.status_code == 201:
            data = response.json()
            click.echo("✓ Backup created successfully!")
            click.echo(f"  Name: {data.get('name')}")
            click.echo(f"  ID: {data.get('id')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_context
def status(ctx):
    """System status commands."""
    pass


@status.command("system")
@click.pass_context
def system_status(ctx):
    """Show system information."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = httpx.get(
            f"{BASE_URL}{API_VERSION}/system",
            headers=get_headers(),
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            click.echo("System Information:")
            click.echo(f"  WireGuard: {'✓ Installed' if data.get('wireguard_installed') else '✗ Not installed'}")
            click.echo(f"  IP Forwarding: {'✓ Enabled' if data.get('ip_forwarding_enabled') else '✗ Disabled'}")
            click.echo(f"  Firewall: {'✓ Configured' if data.get('firewall_configured') else '✗ Not configured'}")
            click.echo(f"  Default Interface: {data.get('default_interface')}")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@status.command("health")
@click.pass_context
def health_check(ctx):
    """Run health check on the system."""
    if not check_api_health():
        sys.exit(1)
    
    try:
        response = httpx.get(
            f"{BASE_URL}/health",
            headers=get_headers(),
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            
            if status == 'healthy':
                click.echo("✓ System health check passed!")
                click.echo(f"  Overall Status: {status}")
                
                if 'details' in data:
                    for component, health in data['details'].items():
                        emoji = "✓" if health else "✗"
                        click.echo(f"  {emoji} {component}")
            else:
                click.echo(f"✗ System health check failed: {status}")
                
        else:
            click.echo(f"Error: {response.status_code} - {response.text}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
