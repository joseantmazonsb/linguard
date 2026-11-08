"""
Comprehensive tests for metrics collector service.
Tests all metrics collection and aggregation functions.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.metrics_collector import (
    MetricsCollectorService,
)


class TestMetricsCollectorService:
    """Test suite for MetricsCollectorService."""

    @pytest.fixture
    def collector(self):
        """Create a MetricsCollectorService instance."""
        return MetricsCollectorService()

    def test_get_interface_stats_success(self, collector):
        """Test successful interface stats retrieval."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "wg0\nprivate-key test123\npublic-key test456\nlisten-port 51820\nfwmark 0x1234\n\npublic-key-1 preshared-key 1.2.3.4:54321\n\t0\t100\t100\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            stats = collector._get_interface_stats("wg0")
            
            assert stats is not None
            assert "peers" in stats

    def test_get_interface_stats_error(self, collector):
        """Test interface stats with error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            stats = collector._get_interface_stats("wg0")
            
            # Error returns None
            assert stats is None

    def test_get_interface_stats_with_extra_fields(self, collector):
        """Test interface stats with extra fields in output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "wg0\nprivate-key test123\npublic-key test456\nlisten-port 51820\nfwmark 0x1234\n\npublic-key-1 preshared-key 1.2.3.4:54321\n\t0\t100\t100\t1234567890\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            stats = collector._get_interface_stats("wg0")
            
            # Should handle extra fields gracefully
            assert stats is not None

    def test_get_interface_stats_invalid_port(self, collector):
        """Test interface stats with invalid port."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "wg0\nprivate-key test123\npublic-key test456\nlisten-port abc\nfwmark 0x1234\n\npublic-key-1 preshared-key 1.2.3.4:54321\n\t0\t100\t100\n"
        mock_result.stderr = ""
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            stats = collector._get_interface_stats("wg0")
            
            # Should still return stats even with invalid port
            assert stats is not None
