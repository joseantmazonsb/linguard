"""Service for collecting WireGuard traffic metrics."""
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.peer import Peer
from ..models.server import Server
from ..models.traffic_metric import TrafficMetric


class MetricsCollectorService:
    """Collects and stores traffic metrics from WireGuard interfaces."""
    
    def __init__(self, wg_binary: str = "wg"):
        """
        Initialize metrics collector service.
        
        Args:
            wg_binary: Path to 'wg' binary (default: "wg" - uses PATH)
        """
        self.wg_binary = wg_binary

    async def collect_all_metrics(self, db: AsyncSession) -> Dict[str, int]:
        """
        Collect metrics for all running servers and their peers.
        
        Returns:
            Dictionary with counts of metrics collected
        """
        result = await db.execute(select(Server).where(Server.status == "running"))
        running_servers = result.scalars().all()
        
        servers_updated = 0
        peers_updated = 0
        
        for server in running_servers:
            try:
                stats = self._get_interface_stats(server.interface)
                if stats:
                    await self._process_server_stats(db, server, stats)
                    servers_updated += 1
                    peers_updated += await self._process_peer_stats(db, server, stats)
            except Exception as e:
                print(f"Error collecting metrics for server {server.name}: {e}")
        
        await db.commit()
        
        # After collecting metrics, broadcast updates via WebSocket
        await self._broadcast_metrics_update(db)
        
        return {
            "servers_updated": servers_updated,
            "peers_updated": peers_updated
        }
    
    async def _broadcast_metrics_update(self, db: AsyncSession):
        """Broadcast current metrics to all connected WebSocket clients."""
        try:
            # Import here to avoid circular dependency
            from ..api.ws import manager
            
            # Get aggregate server metrics
            result = await db.execute(
                select(
                    func.sum(Server.rx_bytes).label('total_rx'),
                    func.sum(Server.tx_bytes).label('total_tx')
                )
            )
            server_totals = result.one()
            
            # Get aggregate peer metrics
            result = await db.execute(
                select(
                    func.sum(Peer.rx_bytes).label('total_rx'),
                    func.sum(Peer.tx_bytes).label('total_tx')
                )
            )
            peer_totals = result.one()
            
            # Get top 5 servers
            result = await db.execute(
                select(Server)
                .order_by((Server.rx_bytes + Server.tx_bytes).desc())
                .limit(5)
            )
            top_servers = result.scalars().all()
            
            # Get top 5 peers
            result = await db.execute(
                select(Peer)
                .order_by((Peer.rx_bytes + Peer.tx_bytes).desc())
                .limit(5)
            )
            top_peers = result.scalars().all()
            
            # Broadcast the update
            await manager.broadcast({
                "type": "metrics_update",
                "data": {
                    "servers": {
                        "total_rx_bytes": int(server_totals.total_rx or 0),
                        "total_tx_bytes": int(server_totals.total_tx or 0),
                        "top_servers": [
                            {
                                "id": s.id,
                                "name": s.name,
                                "rx_bytes": s.rx_bytes or 0,
                                "tx_bytes": s.tx_bytes or 0,
                            }
                            for s in top_servers
                        ]
                    },
                    "peers": {
                        "total_rx_bytes": int(peer_totals.total_rx or 0),
                        "total_tx_bytes": int(peer_totals.total_tx or 0),
                        "top_peers": [
                            {
                                "id": p.id,
                                "name": p.name,
                                "rx_bytes": p.rx_bytes or 0,
                                "tx_bytes": p.tx_bytes or 0,
                            }
                            for p in top_peers
                        ]
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            })
        except Exception as e:
            print(f"Error broadcasting metrics update: {e}")

    def _get_interface_stats(self, interface: str) -> Optional[Dict]:
        """
        Get WireGuard interface statistics using 'wg show' command.
        
        Args:
            interface: WireGuard interface name (e.g., wg0)
            
        Returns:
            Dictionary with peer stats or None if interface not found
        """
        try:
            result = subprocess.run(
                [self.wg_binary, "show", interface, "dump"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            lines = result.stdout.strip().split('\n')
            if not lines:
                return None
            
            # First line is the interface itself, rest are peers
            # Format: private-key public-key listen-port fwmark
            # Peer format: public-key preshared-key endpoint allowed-ips latest-handshake rx-bytes tx-bytes persistent-keepalive
            
            stats = {
                'peers': {}
            }
            
            for line in lines[1:]:  # Skip interface line
                parts = line.split('\t')
                if len(parts) >= 8:
                    public_key = parts[0]
                    latest_handshake = int(parts[4]) if parts[4] != '0' else None
                    rx_bytes = int(parts[5])
                    tx_bytes = int(parts[6])
                    
                    stats['peers'][public_key] = {
                        'rx_bytes': rx_bytes,
                        'tx_bytes': tx_bytes,
                        'latest_handshake': latest_handshake,
                        'is_connected': latest_handshake is not None
                    }
            
            return stats
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as e:
            print(f"Error getting stats for {interface}: {e}")
            return None

    async def _process_server_stats(self, db: AsyncSession, server: Server, stats: Dict):
        """Calculate and store server aggregate statistics."""
        # Sum up all peer traffic for server totals
        total_rx = 0
        total_tx = 0
        
        for peer_stats in stats['peers'].values():
            total_rx += peer_stats['rx_bytes']
            total_tx += peer_stats['tx_bytes']
        
        # Calculate delta
        rx_delta = total_rx - (server.rx_bytes or 0)
        tx_delta = total_tx - (server.tx_bytes or 0)
        
        # Update server current stats
        server.rx_bytes = total_rx
        server.tx_bytes = total_tx
        
        # Store historical metric
        metric = TrafficMetric(
            server_id=server.id,
            rx_bytes=total_rx,
            tx_bytes=total_tx,
            rx_bytes_delta=max(0, rx_delta),  # Ensure non-negative
            tx_bytes_delta=max(0, tx_delta),
            is_connected=len(stats['peers']) > 0,
            recorded_at=datetime.now(timezone.utc)
        )
        db.add(metric)

    async def _process_peer_stats(self, db: AsyncSession, server: Server, stats: Dict) -> int:
        """Process and store peer statistics."""
        peers_updated = 0
        
        # Get all peers for this server
        result = await db.execute(
            select(Peer).where(Peer.server_id == server.id)
        )
        peers = result.scalars().all()
        
        for peer in peers:
            if peer.public_key in stats['peers']:
                peer_stats = stats['peers'][peer.public_key]
                
                # Calculate delta
                rx_delta = peer_stats['rx_bytes'] - (peer.rx_bytes or 0)
                tx_delta = peer_stats['tx_bytes'] - (peer.tx_bytes or 0)
                
                # Update peer current stats
                peer.rx_bytes = peer_stats['rx_bytes']
                peer.tx_bytes = peer_stats['tx_bytes']
                
                # Update handshake time
                if peer_stats['latest_handshake']:
                    peer.last_handshake = datetime.fromtimestamp(
                        peer_stats['latest_handshake'],
                        tz=timezone.utc
                    )
                
                # Store historical metric
                metric = TrafficMetric(
                    peer_id=peer.id,
                    rx_bytes=peer_stats['rx_bytes'],
                    tx_bytes=peer_stats['tx_bytes'],
                    rx_bytes_delta=max(0, rx_delta),
                    tx_bytes_delta=max(0, tx_delta),
                    handshake_at=peer.last_handshake,
                    is_connected=peer_stats['is_connected'],
                    recorded_at=datetime.now(timezone.utc)
                )
                db.add(metric)
                peers_updated += 1
        
        return peers_updated
