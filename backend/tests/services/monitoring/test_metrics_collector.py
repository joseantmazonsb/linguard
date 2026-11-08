"""Tests for MetricsCollectorService: `wg show` parsing and metric persistence."""

import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.metrics_collector as collector_module
from app.models.peer import Peer
from app.models.server import Server
from app.models.traffic_metric import TrafficMetric
from app.services.metrics_collector import MetricsCollectorService

SERVER_PUB = "aGVsbG8td29ybGQtc2VydmVyLXB1YmxpYy1rZXkteHl6MTIzNDU="
PEER1_PUB = "cGVlci1vbmUtcHVibGljLWtleS1hYmNkZWZnaGlqa2xtbm9wcXJzdHU="
PEER2_PUB = "cGVlci10d28tcHVibGljLWtleS1hYmNkZWZnaGlqa2xtbm9wcXJzdHU="

# Realistic `wg show wg0 dump` output: interface line + two peers (one idle).
WG_DUMP = (
    f"{SERVER_PUB}\t{SERVER_PUB}\t51820\toff\n"
    f"{PEER1_PUB}\t(none)\t203.0.113.7:51820\t10.66.66.2/32\t1700000000\t1024\t2048\t25\n"
    f"{PEER2_PUB}\t(none)\t(none)\t10.66.66.3/32\t0\t0\t0\toff\n"
)


@pytest.fixture
def collector():
    return MetricsCollectorService(wg_binary="/usr/bin/wg")


async def _seed_server(db_session, name="wg-server", status="running", interface="wg0", **kwargs):
    server = Server(
        name=name,
        interface=interface,
        public_key=SERVER_PUB,
        private_key="private-key-value",
        listen_port=51820,
        status=status,
        rx_bytes=kwargs.pop("rx_bytes", 0),
        tx_bytes=kwargs.pop("tx_bytes", 0),
        **kwargs,
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)
    return server


async def _seed_peer(db_session, server, name, public_key, rx_bytes=0, tx_bytes=0):
    peer = Peer(
        server_id=server.id,
        name=name,
        public_key=public_key,
        private_key="peer-private",
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
    )
    db_session.add(peer)
    await db_session.commit()
    await db_session.refresh(peer)
    return peer


# ----------------------------------------------------------------------------
# `wg show <if> dump` parsing
# ----------------------------------------------------------------------------


def test_should_parse_peer_stats_when_wg_dump_has_peers(collector):
    with patch.object(
        collector_module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout=WG_DUMP, stderr=""),
    ) as run:
        stats = collector._get_interface_stats("wg0")

    run.assert_called_once_with(
        ["/usr/bin/wg", "show", "wg0", "dump"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert set(stats["peers"]) == {PEER1_PUB, PEER2_PUB}
    connected = stats["peers"][PEER1_PUB]
    assert connected == {
        "rx_bytes": 1024,
        "tx_bytes": 2048,
        "latest_handshake": 1700000000,
        "is_connected": True,
    }
    idle = stats["peers"][PEER2_PUB]
    assert idle["latest_handshake"] is None
    assert idle["is_connected"] is False
    assert idle["rx_bytes"] == 0


def test_should_return_no_peers_when_dump_only_has_interface_line(collector):
    interface_only = f"{SERVER_PUB}\t{SERVER_PUB}\t51820\toff\n"
    with patch.object(
        collector_module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout=interface_only, stderr=""),
    ):
        stats = collector._get_interface_stats("wg0")

    assert stats == {"peers": {}}


def test_should_ignore_malformed_peer_lines_when_dump_is_truncated(collector):
    truncated = f"{SERVER_PUB}\t{SERVER_PUB}\t51820\toff\n{PEER1_PUB}\t(none)\t1.2.3.4\n"
    with patch.object(
        collector_module.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout=truncated, stderr=""),
    ):
        stats = collector._get_interface_stats("wg0")

    assert stats == {"peers": {}}


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["wg"]),  # interface missing / no permission
        FileNotFoundError("wg"),
        subprocess.TimeoutExpired(["wg"], 5),
        ValueError("unexpected"),
    ],
)
def test_should_return_none_when_wg_command_fails(collector, error):
    with patch.object(collector_module.subprocess, "run", side_effect=error):
        assert collector._get_interface_stats("wg0") is None


# ----------------------------------------------------------------------------
# Full collection cycle
# ----------------------------------------------------------------------------


async def test_should_store_server_and_peer_metrics_when_server_running(collector, api_db, db_session):
    server = await _seed_server(db_session, rx_bytes=500, tx_bytes=100)
    peer1 = await _seed_peer(db_session, server, "peer-1", PEER1_PUB, rx_bytes=100, tx_bytes=50)
    peer2 = await _seed_peer(db_session, server, "peer-2", PEER2_PUB)

    broadcast = AsyncMock()
    with patch.object(collector, "_get_interface_stats", return_value={
        "peers": {
            PEER1_PUB: {"rx_bytes": 1024, "tx_bytes": 2048, "latest_handshake": 1700000000, "is_connected": True},
            PEER2_PUB: {"rx_bytes": 0, "tx_bytes": 0, "latest_handshake": None, "is_connected": False},
        }
    }), patch("app.api.ws.manager.broadcast", broadcast):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 1, "peers_updated": 2}

    await db_session.refresh(server)
    assert (server.rx_bytes, server.tx_bytes) == (1024, 2048)

    await db_session.refresh(peer1)
    assert (peer1.rx_bytes, peer1.tx_bytes) == (1024, 2048)
    # SQLite drops tzinfo on read-back, so compare the wall clock value
    assert peer1.last_handshake.replace(tzinfo=UTC) == datetime.fromtimestamp(
        1700000000, tz=UTC
    )

    await db_session.refresh(peer2)
    assert (peer2.rx_bytes, peer2.tx_bytes) == (0, 0)
    assert peer2.last_handshake is None

    metrics = (await db_session.execute(select(TrafficMetric))).scalars().all()
    assert len(metrics) == 3
    server_metric = next(m for m in metrics if m.server_id == server.id)
    assert server_metric.rx_bytes == 1024
    assert server_metric.rx_bytes_delta == 524  # 1024 - 500 previous
    assert server_metric.tx_bytes_delta == 1948  # 2048 - 100 previous
    assert server_metric.is_connected is True

    peer_metric = next(m for m in metrics if m.peer_id == peer1.id)
    assert peer_metric.rx_bytes_delta == 924
    assert peer_metric.is_connected is True
    assert peer_metric.handshake_at.replace(tzinfo=None) == peer1.last_handshake


async def test_should_clamp_delta_to_zero_when_counters_reset(collector, api_db, db_session):
    server = await _seed_server(db_session, rx_bytes=9999, tx_bytes=9999)
    await _seed_peer(db_session, server, "peer-1", PEER1_PUB, rx_bytes=9999, tx_bytes=9999)

    with patch.object(collector, "_get_interface_stats", return_value={
        "peers": {PEER1_PUB: {"rx_bytes": 10, "tx_bytes": 20, "latest_handshake": None, "is_connected": False}}
    }), patch("app.api.ws.manager.broadcast", AsyncMock()):
        await collector.collect_all_metrics(db_session)

    metrics = (await db_session.execute(select(TrafficMetric))).scalars().all()
    assert all(m.rx_bytes_delta == 0 and m.tx_bytes_delta == 0 for m in metrics)


async def test_should_skip_stopped_servers_when_collecting(collector, api_db, db_session):
    await _seed_server(db_session, name="stopped", status="stopped", interface="wg9")
    get_stats = MagicMock()

    with patch.object(collector, "_get_interface_stats", get_stats), \
         patch("app.api.ws.manager.broadcast", AsyncMock()):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 0, "peers_updated": 0}
    get_stats.assert_not_called()


async def test_should_continue_when_one_server_fails(collector, api_db, db_session):
    good = await _seed_server(db_session, name="good", interface="wg0")
    await _seed_server(db_session, name="bad", interface="wg1")

    def stats_for(interface):
        if interface == "wg1":
            raise RuntimeError("boom")
        return {"peers": {PEER1_PUB: {"rx_bytes": 1, "tx_bytes": 2, "latest_handshake": None, "is_connected": False}}}

    await _seed_peer(db_session, good, "peer-1", PEER1_PUB)
    with patch.object(collector, "_get_interface_stats", side_effect=stats_for), \
         patch("app.api.ws.manager.broadcast", AsyncMock()):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 1, "peers_updated": 1}


async def test_should_skip_update_when_interface_has_no_stats(collector, api_db, db_session):
    await _seed_server(db_session)

    with patch.object(collector, "_get_interface_stats", return_value=None), \
         patch("app.api.ws.manager.broadcast", AsyncMock()):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 0, "peers_updated": 0}
    assert (await db_session.execute(select(TrafficMetric))).scalars().all() == []


async def test_should_ignore_peers_unknown_to_wireguard_when_collecting(collector, api_db, db_session):
    server = await _seed_server(db_session)
    await _seed_peer(db_session, server, "ghost", "unknown-public-key")

    with patch.object(collector, "_get_interface_stats", return_value={
        "peers": {PEER1_PUB: {"rx_bytes": 1, "tx_bytes": 2, "latest_handshake": None, "is_connected": True}}
    }), patch("app.api.ws.manager.broadcast", AsyncMock()):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 1, "peers_updated": 0}


# ----------------------------------------------------------------------------
# WebSocket broadcast
# ----------------------------------------------------------------------------


async def test_should_broadcast_aggregated_metrics_when_collection_finishes(collector, api_db, db_session):
    server = await _seed_server(db_session, name="alpha", rx_bytes=100, tx_bytes=200)
    peer = await _seed_peer(db_session, server, "peer-1", PEER1_PUB, rx_bytes=10, tx_bytes=20)
    broadcast = AsyncMock()

    with patch.object(collector, "_get_interface_stats", return_value=None), \
         patch("app.api.ws.manager.broadcast", broadcast):
        await collector.collect_all_metrics(db_session)

    broadcast.assert_awaited_once()
    message = broadcast.await_args.args[0]
    assert message["type"] == "metrics_update"
    data = message["data"]
    assert data["servers"]["total_rx_bytes"] == 100
    assert data["servers"]["total_tx_bytes"] == 200
    assert data["servers"]["top_servers"][0]["name"] == "alpha"
    assert data["peers"]["total_rx_bytes"] == 10
    assert data["peers"]["top_peers"][0]["id"] == peer.id
    assert "timestamp" in data


async def test_should_return_counts_when_broadcast_fails(collector, api_db, db_session):
    server = await _seed_server(db_session)
    assert server.id

    with patch.object(collector, "_get_interface_stats", return_value=None), \
         patch("app.api.ws.manager.broadcast", AsyncMock(side_effect=RuntimeError("no clients"))):
        result = await collector.collect_all_metrics(db_session)

    assert result == {"servers_updated": 0, "peers_updated": 0}
