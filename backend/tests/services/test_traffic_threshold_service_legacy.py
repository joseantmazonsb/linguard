"""
Tests for traffic_threshold_service.py
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock
from app.services.traffic_threshold_service import (
    TrafficThresholdService,
    TrafficDirection,
    TimeWindow,
)


class TestTrafficThresholdService:
    """Test suite for TrafficThresholdService."""

    @pytest.fixture
    def service(self):
        """Create a TrafficThresholdService instance."""
        return TrafficThresholdService()

    # ------------------------------------------------------------------
    # Test _validate_threshold_bytes
    # ------------------------------------------------------------------

    def test_validate_threshold_bytes_valid(self):
        """Test validating a valid threshold bytes value."""
        service = TrafficThresholdService()
        assert service._validate_threshold_bytes(1000) is True
        assert service._validate_threshold_bytes(1000.5) is True

    def test_validate_threshold_bytes_invalid_type(self):
        """Test validating threshold bytes with invalid type."""
        service = TrafficThresholdService()
        assert service._validate_threshold_bytes("1000") is False
        assert service._validate_threshold_bytes(None) is False

    def test_validate_threshold_bytes_zero(self):
        """Test validating threshold bytes with zero value."""
        service = TrafficThresholdService()
        assert service._validate_threshold_bytes(0) is False
        assert service._validate_threshold_bytes(-100) is False

    # ------------------------------------------------------------------
    # Test _validate_time_window
    # ------------------------------------------------------------------

    def test_validate_time_window_valid(self):
        """Test validating a valid time window."""
        service = TrafficThresholdService()
        assert service._validate_time_window(TimeWindow.LAST_HOUR.value) is True
        assert service._validate_time_window(TimeWindow.LAST_24_HOURS.value) is True

    def test_validate_time_window_invalid(self):
        """Test validating an invalid time window."""
        service = TrafficThresholdService()
        assert service._validate_time_window("invalid") is False

    # ------------------------------------------------------------------
    # Test _validate_metrics
    # ------------------------------------------------------------------

    def test_validate_metrics_valid(self):
        """Test validating valid metrics data."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": 1000, "tx_bytes": 2000},
            "peer2": {"rx_bytes": 1500, "tx_bytes": 2500},
        }
        assert service._validate_metrics(metrics) is True

    def test_validate_metrics_missing_fields(self):
        """Test validating metrics with missing fields."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": 1000},  # Missing tx_bytes
        }
        assert service._validate_metrics(metrics) is False

    def test_validate_metrics_invalid_types(self):
        """Test validating metrics with invalid types."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": "1000", "tx_bytes": 2000},
        }
        assert service._validate_metrics(metrics) is False

    # ------------------------------------------------------------------
    # Test _get_relevant_metrics
    # ------------------------------------------------------------------

    def test_get_relevant_metrics_combined(self):
        """Test getting relevant metrics with combined direction."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": 1000, "tx_bytes": 2000},
            "peer2": {"rx_bytes": 1500, "tx_bytes": 2500},
        }
        relevant = service._get_relevant_metrics(metrics, TrafficDirection.COMBINED)
        assert len(relevant) == 2

    def test_get_relevant_metrics_inbound(self):
        """Test getting relevant metrics with inbound direction."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": 1000, "tx_bytes": 2000},
        }
        relevant = service._get_relevant_metrics(metrics, TrafficDirection.INBOUND)
        assert any(m.get("rx_bytes", 0) > 0 for m in relevant)

    def test_get_relevant_metrics_outbound(self):
        """Test getting relevant metrics with outbound direction."""
        service = TrafficThresholdService()
        metrics = {
            "peer1": {"rx_bytes": 1000, "tx_bytes": 2000},
        }
        relevant = service._get_relevant_metrics(metrics, TrafficDirection.OUTBOUND)
        assert any(m.get("tx_bytes", 0) > 0 for m in relevant)

    # ------------------------------------------------------------------
    # Test _get_all_peer_metrics
    # ------------------------------------------------------------------

    def test_get_all_peer_metrics_simple(self):
        """Test getting all peer metrics with simple structure."""
        service = TrafficThresholdService()
        peer_metrics = {"rx_bytes": 1000, "tx_bytes": 2000}
        metrics = service._get_all_peer_metrics(peer_metrics)
        assert len(metrics) == 1

    def test_get_all_peer_metrics_with_metrics_key(self):
        """Test getting all peer metrics with metrics key."""
        service = TrafficThresholdService()
        peer_metrics = {"metrics": [{"rx_bytes": 1000, "tx_bytes": 2000}]}
        metrics = service._get_all_peer_metrics(peer_metrics)
        assert len(metrics) == 1

    # ------------------------------------------------------------------
    # Test get_threshold_recommendation
    # ------------------------------------------------------------------

    def test_get_threshold_recommendation_low_traffic(self):
        """Test getting threshold recommendation with low traffic."""
        service = TrafficThresholdService()
        result = service.get_threshold_recommendation(100)
        assert result["recommended_threshold"] == 110
        assert result["safety_margin"] == 10

    def test_get_threshold_recommendation_zero_traffic(self):
        """Test getting threshold recommendation with zero traffic."""
        service = TrafficThresholdService()
        result = service.get_threshold_recommendation(0)
        assert result["recommended_threshold"] == 0
        assert result["reason"] == "No traffic detected"

    # ------------------------------------------------------------------
    # Test calculate_traffic_percent
    # ------------------------------------------------------------------

    def test_calculate_traffic_percent_zero_threshold(self):
        """Test calculating traffic percent with zero threshold."""
        service = TrafficThresholdService()
        percent = service.calculate_traffic_percent(1000, 0)
        assert percent == 0.0

    def test_calculate_traffic_percent_50_percent(self):
        """Test calculating traffic percent at 50%."""
        service = TrafficThresholdService()
        percent = service.calculate_traffic_percent(5000, 10000)
        assert percent == 50.0

    def test_calculate_traffic_percent_over_threshold(self):
        """Test calculating traffic percent over threshold."""
        service = TrafficThresholdService()
        percent = service.calculate_traffic_percent(15000, 10000)
        assert percent > 100.0

    # ------------------------------------------------------------------
    # Test format_traffic_bytes
    # ------------------------------------------------------------------

    def test_format_traffic_bytes_small(self):
        """Test formatting small byte values."""
        service = TrafficThresholdService()
        formatted = service.format_traffic_bytes(1024)
        assert "KB" in formatted

    def test_format_traffic_bytes_large(self):
        """Test formatting large byte values."""
        service = TrafficThresholdService()
        formatted = service.format_traffic_bytes(1048576)
        assert "MB" in formatted

    # ------------------------------------------------------------------
    # Test evaluate_threshold
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_evaluate_threshold_exceeded(self):
        """Test evaluating threshold when it's exceeded."""
        service = TrafficThresholdService()
        result = await service.evaluate_threshold(
            threshold_bytes=3000,
            metrics={"peer1": {"rx_bytes": 1000, "tx_bytes": 2000}},
            time_window=TimeWindow.LAST_HOUR.value,
            direction=TrafficDirection.COMBINED,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_threshold_not_exceeded(self):
        """Test evaluating threshold when it's not exceeded."""
        service = TrafficThresholdService()
        result = await service.evaluate_threshold(
            threshold_bytes=10000,
            metrics={"peer1": {"rx_bytes": 1000, "tx_bytes": 2000}},
            time_window=TimeWindow.LAST_HOUR.value,
            direction=TrafficDirection.COMBINED,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_evaluate_threshold_invalid_threshold(self):
        """Test evaluating threshold with invalid threshold bytes."""
        service = TrafficThresholdService()
        with pytest.raises(ValueError, match="threshold_bytes must be a positive number"):
            await service.evaluate_threshold(
                threshold_bytes=-1,
                metrics={"peer1": {"rx_bytes": 1000, "tx_bytes": 2000}},
                time_window=TimeWindow.LAST_HOUR.value,
                direction=TrafficDirection.COMBINED,
            )

    # ------------------------------------------------------------------
    # Test evaluate_peer_thresholds
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_evaluate_peer_thresholds_all_exceeded(self):
        """Test evaluating multiple thresholds when all are exceeded."""
        service = TrafficThresholdService()
        thresholds = [
            {"threshold_bytes": 3000, "time_window": TimeWindow.LAST_HOUR.value, "direction": TrafficDirection.COMBINED, "enabled": True},
        ]
        result = await service.evaluate_peer_thresholds(
            peer_id="peer1",
            peer_metrics={"rx_bytes": 1000, "tx_bytes": 2000},
            thresholds=thresholds,
        )
        assert len(result) == 1
        assert result[0]["exceeded"] is True

    # ------------------------------------------------------------------
    # Test validate_threshold_config
    # ------------------------------------------------------------------

    def test_validate_threshold_config_valid(self):
        """Test validating a valid threshold configuration."""
        service = TrafficThresholdService()
        config = {
            "threshold_bytes": 1000,
            "time_window": TimeWindow.LAST_HOUR.value,
            "direction": TrafficDirection.COMBINED.value,
        }
        errors = service.validate_threshold_config(config)
        assert len(errors) == 0

    def test_validate_threshold_config_missing_fields(self):
        """Test validating a threshold configuration with missing fields."""
        service = TrafficThresholdService()
        config = {"threshold_bytes": 1000}
        errors = service.validate_threshold_config(config)
        assert len(errors) > 0
        assert "time_window is required" in errors
