"""API endpoints for traffic metrics."""
from datetime import datetime, timedelta, timezone
from typing import List

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.peer import Peer
from ..models.server import Server
from ..models.traffic_metric import TrafficMetric
from ..models.user import User
from ..services.metrics_collector import MetricsCollectorService

router = APIRouter()


@router.post("/collect")
@inject
async def collect_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    metrics_collector: MetricsCollectorService = Depends(Provide[Container.metrics_collector_service])
):
    """Manually trigger metrics collection for all running servers."""
    result = await metrics_collector.collect_all_metrics(db)
    return {
        "status": "success",
        "servers_updated": result["servers_updated"],
        "peers_updated": result["peers_updated"]
    }


@router.get("/server/{server_id}")
async def get_server_metrics(
    server_id: int,
    hours: int = Query(24, description="Number of hours of historical data", ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get traffic metrics for a specific server."""
    # Verify server exists
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    
    if not server:
        return {"error": "Server not found"}, 404
    
    # Get historical metrics
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(TrafficMetric)
        .where(
            and_(
                TrafficMetric.server_id == server_id,
                TrafficMetric.recorded_at >= cutoff_time
            )
        )
        .order_by(TrafficMetric.recorded_at)
    )
    metrics = result.scalars().all()
    
    return {
        "server": {
            "id": server.id,
            "name": server.name,
            "current_rx_bytes": server.rx_bytes or 0,
            "current_tx_bytes": server.tx_bytes or 0
        },
        "metrics": [
            {
                "recorded_at": m.recorded_at.isoformat(),
                "rx_bytes": m.rx_bytes,
                "tx_bytes": m.tx_bytes,
                "rx_bytes_delta": m.rx_bytes_delta,
                "tx_bytes_delta": m.tx_bytes_delta,
                "is_connected": m.is_connected
            }
            for m in metrics
        ],
        "summary": {
            "total_data_points": len(metrics),
            "time_range_hours": hours
        }
    }


@router.get("/peer/{peer_id}")
async def get_peer_metrics(
    peer_id: int,
    hours: int = Query(24, description="Number of hours of historical data", ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get traffic metrics for a specific peer."""
    # Verify peer exists
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()
    
    if not peer:
        return {"error": "Peer not found"}, 404
    
    # Get historical metrics
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(TrafficMetric)
        .where(
            and_(
                TrafficMetric.peer_id == peer_id,
                TrafficMetric.recorded_at >= cutoff_time
            )
        )
        .order_by(TrafficMetric.recorded_at)
    )
    metrics = result.scalars().all()
    
    return {
        "peer": {
            "id": peer.id,
            "name": peer.name,
            "current_rx_bytes": peer.rx_bytes or 0,
            "current_tx_bytes": peer.tx_bytes or 0,
            "last_handshake": peer.last_handshake.isoformat() if peer.last_handshake else None
        },
        "metrics": [
            {
                "recorded_at": m.recorded_at.isoformat(),
                "rx_bytes": m.rx_bytes,
                "tx_bytes": m.tx_bytes,
                "rx_bytes_delta": m.rx_bytes_delta,
                "tx_bytes_delta": m.tx_bytes_delta,
                "is_connected": m.is_connected,
                "handshake_at": m.handshake_at.isoformat() if m.handshake_at else None
            }
            for m in metrics
        ],
        "summary": {
            "total_data_points": len(metrics),
            "time_range_hours": hours
        }
    }


@router.get("/servers/aggregate")
async def get_servers_aggregate_metrics(
    hours: int = Query(24, description="Number of hours of historical data", ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregate traffic metrics for all servers."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Get server metrics aggregated by time
    result = await db.execute(
        select(
            func.strftime('%Y-%m-%d %H:00:00', TrafficMetric.recorded_at).label('hour'),
            func.sum(TrafficMetric.rx_bytes_delta).label('total_rx'),
            func.sum(TrafficMetric.tx_bytes_delta).label('total_tx')
        )
        .where(
            and_(
                TrafficMetric.recorded_at >= cutoff_time,
                TrafficMetric.server_id.isnot(None)
            )
        )
        .group_by('hour')
        .order_by('hour')
    )
    hourly_stats = result.all()
    
    # Get current totals for all servers
    result = await db.execute(
        select(
            func.sum(Server.rx_bytes).label('total_rx'),
            func.sum(Server.tx_bytes).label('total_tx')
        )
    )
    current_totals = result.one()
    
    # Get all servers with their traffic
    result = await db.execute(
        select(Server)
        .order_by(desc(Server.rx_bytes + Server.tx_bytes))
    )
    servers = result.scalars().all()
    
    return {
        "current_totals": {
            "total_rx_bytes": int(current_totals.total_rx or 0),
            "total_tx_bytes": int(current_totals.total_tx or 0)
        },
        "hourly_metrics": [
            {
                "timestamp": row.hour,
                "rx_bytes": int(row.total_rx or 0),
                "tx_bytes": int(row.total_tx or 0)
            }
            for row in hourly_stats
        ],
        "servers": [
            {
                "id": s.id,
                "name": s.name,
                "rx_bytes": s.rx_bytes or 0,
                "tx_bytes": s.tx_bytes or 0,
                "total_bytes": (s.rx_bytes or 0) + (s.tx_bytes or 0)
            }
            for s in servers
        ],
        "summary": {
            "time_range_hours": hours,
            "total_servers": len(servers)
        }
    }


@router.get("/peers/aggregate")
async def get_peers_aggregate_metrics(
    hours: int = Query(24, description="Number of hours of historical data", ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregate traffic metrics for all peers."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Get peer metrics aggregated by time
    result = await db.execute(
        select(
            func.strftime('%Y-%m-%d %H:00:00', TrafficMetric.recorded_at).label('hour'),
            func.sum(TrafficMetric.rx_bytes_delta).label('total_rx'),
            func.sum(TrafficMetric.tx_bytes_delta).label('total_tx')
        )
        .where(
            and_(
                TrafficMetric.recorded_at >= cutoff_time,
                TrafficMetric.peer_id.isnot(None)
            )
        )
        .group_by('hour')
        .order_by('hour')
    )
    hourly_stats = result.all()
    
    # Get current totals for all peers
    result = await db.execute(
        select(
            func.sum(Peer.rx_bytes).label('total_rx'),
            func.sum(Peer.tx_bytes).label('total_tx')
        )
    )
    current_totals = result.one()
    
    # Get all peers with their traffic
    result = await db.execute(
        select(Peer)
        .order_by(desc(Peer.rx_bytes + Peer.tx_bytes))
    )
    peers = result.scalars().all()
    
    return {
        "current_totals": {
            "total_rx_bytes": int(current_totals.total_rx or 0),
            "total_tx_bytes": int(current_totals.total_tx or 0)
        },
        "hourly_metrics": [
            {
                "timestamp": row.hour,
                "rx_bytes": int(row.total_rx or 0),
                "tx_bytes": int(row.total_tx or 0)
            }
            for row in hourly_stats
        ],
        "peers": [
            {
                "id": p.id,
                "name": p.name,
                "rx_bytes": p.rx_bytes or 0,
                "tx_bytes": p.tx_bytes or 0,
                "total_bytes": (p.rx_bytes or 0) + (p.tx_bytes or 0)
            }
            for p in peers
        ],
        "summary": {
            "time_range_hours": hours,
            "total_peers": len(peers)
        }
    }


@router.get("/dashboard")
async def get_dashboard_metrics(
    hours: int = Query(24, description="Number of hours of historical data", ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregate traffic metrics for dashboard overview (both servers and peers)."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Get server metrics aggregated by time
    result = await db.execute(
        select(
            func.strftime('%Y-%m-%d %H:00:00', TrafficMetric.recorded_at).label('hour'),
            func.sum(TrafficMetric.rx_bytes_delta).label('total_rx'),
            func.sum(TrafficMetric.tx_bytes_delta).label('total_tx')
        )
        .where(
            and_(
                TrafficMetric.recorded_at >= cutoff_time,
                TrafficMetric.server_id.isnot(None)
            )
        )
        .group_by('hour')
        .order_by('hour')
    )
    server_hourly_stats = result.all()
    
    # Get peer metrics aggregated by time
    result = await db.execute(
        select(
            func.strftime('%Y-%m-%d %H:00:00', TrafficMetric.recorded_at).label('hour'),
            func.sum(TrafficMetric.rx_bytes_delta).label('total_rx'),
            func.sum(TrafficMetric.tx_bytes_delta).label('total_tx')
        )
        .where(
            and_(
                TrafficMetric.recorded_at >= cutoff_time,
                TrafficMetric.peer_id.isnot(None)
            )
        )
        .group_by('hour')
        .order_by('hour')
    )
    peer_hourly_stats = result.all()
    
    # Get current totals for servers
    result = await db.execute(
        select(
            func.sum(Server.rx_bytes).label('total_rx'),
            func.sum(Server.tx_bytes).label('total_tx')
        )
    )
    server_totals = result.one()
    
    # Get current totals for peers
    result = await db.execute(
        select(
            func.sum(Peer.rx_bytes).label('total_rx'),
            func.sum(Peer.tx_bytes).label('total_tx')
        )
    )
    peer_totals = result.one()
    
    # Get top 5 servers by traffic
    result = await db.execute(
        select(Server)
        .order_by(desc(Server.rx_bytes + Server.tx_bytes))
        .limit(5)
    )
    top_servers = result.scalars().all()
    
    # Get top 5 peers by traffic
    result = await db.execute(
        select(Peer)
        .order_by(desc(Peer.rx_bytes + Peer.tx_bytes))
        .limit(5)
    )
    top_peers = result.scalars().all()
    
    return {
        "servers": {
            "current_totals": {
                "total_rx_bytes": int(server_totals.total_rx or 0),
                "total_tx_bytes": int(server_totals.total_tx or 0)
            },
            "hourly_metrics": [
                {
                    "timestamp": row.hour,
                    "rx_bytes": int(row.total_rx or 0),
                    "tx_bytes": int(row.total_tx or 0)
                }
                for row in server_hourly_stats
            ],
            "top_servers": [
                {
                    "id": s.id,
                    "name": s.name,
                    "rx_bytes": s.rx_bytes or 0,
                    "tx_bytes": s.tx_bytes or 0,
                    "total_bytes": (s.rx_bytes or 0) + (s.tx_bytes or 0)
                }
                for s in top_servers
            ]
        },
        "peers": {
            "current_totals": {
                "total_rx_bytes": int(peer_totals.total_rx or 0),
                "total_tx_bytes": int(peer_totals.total_tx or 0)
            },
            "hourly_metrics": [
                {
                    "timestamp": row.hour,
                    "rx_bytes": int(row.total_rx or 0),
                    "tx_bytes": int(row.total_tx or 0)
                }
                for row in peer_hourly_stats
            ],
            "top_peers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "rx_bytes": p.rx_bytes or 0,
                    "tx_bytes": p.tx_bytes or 0,
                    "total_bytes": (p.rx_bytes or 0) + (p.tx_bytes or 0)
                }
                for p in top_peers
            ]
        },
        "summary": {
            "time_range_hours": hours
        }
    }
