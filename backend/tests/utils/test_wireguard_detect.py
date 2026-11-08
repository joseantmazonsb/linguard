"""
Comprehensive tests for wireguard_detect module.
Tests all detection and verification functions.
"""
import subprocess
import pytest
from unittest.mock import MagicMock, patch, Mock
from app.utils.wireguard_detect import (
    detect_wireguard_binaries,
    verify_wireguard_binary,
    get_wireguard_paths,
)


class TestDetectWireguardBinaries:
    """Tests for detect_wireguard_binaries function."""

    def test_detect_wireguard_not_found(self):
        """Test detection when wg binary is not found."""
        with patch('shutil.which', return_value=None):
            result = detect_wireguard_binaries()
            
            assert result == {'wg': None}

    def test_detect_wireguard_found_in_path(self):
        """Test detection when wg binary is in PATH."""
        mock_path = "/usr/bin/wg"
        with patch('shutil.which', return_value=mock_path):
            with patch('os.path.isfile', return_value=True):
                with patch('os.access', return_value=True):
                    result = detect_wireguard_binaries()
                    
                    assert result == {'wg': mock_path}

    def test_detect_wireguard_not_executable(self):
        """Test detection when wg exists but is not executable."""
        mock_path = "/usr/bin/wg"
        with patch('shutil.which', return_value=mock_path):
            with patch('os.path.isfile', return_value=True):
                with patch('os.access', return_value=False):
                    result = detect_wireguard_binaries()
                    
                    assert result == {'wg': None}

    def test_detect_wireguard_not_a_file(self):
        """Test detection when wg path is not a file."""
        mock_path = "/usr/bin/wg"
        with patch('shutil.which', return_value=mock_path):
            with patch('os.path.isfile', return_value=False):
                with patch('os.access', return_value=True):
                    result = detect_wireguard_binaries()
                    
                    assert result == {'wg': None}

    def test_detect_wireguard_empty_result(self):
        """Test detection returns empty dict."""
        with patch('shutil.which', return_value=None):
            result = detect_wireguard_binaries()
            
            assert result == {'wg': None}


class TestVerifyWireguardBinary:
    """Tests for verify_wireguard_binary function."""

    def test_verify_invalid_path(self):
        """Test verification fails for invalid path."""
        result = verify_wireguard_binary("/nonexistent/path")
        assert result is False

    def test_verify_empty_path(self):
        """Test verification fails for empty path."""
        result = verify_wireguard_binary("")
        assert result is False

    def test_verify_not_a_file(self):
        """Test verification fails when path is not a file."""
        with patch('os.path.isfile', return_value=False):
            result = verify_wireguard_binary("/some/path")
            assert result is False

    def test_verify_not_executable(self):
        """Test verification fails when path is not executable."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.access', return_value=False):
                result = verify_wireguard_binary("/some/path")
                assert result is False

    def test_verify_version_success(self):
        """Test verification succeeds when --version returns 0."""
        with patch('subprocess.run', return_value=Mock(returncode=0)):
            result = verify_wireguard_binary("/usr/bin/wg")
            assert result is True

    def test_verify_version_failure(self):
        """Test verification fails when --version returns non-zero."""
        with patch('subprocess.run', return_value=Mock(returncode=1)):
            result = verify_wireguard_binary("/usr/bin/wg")
            assert result is False

    def test_verify_timeout(self):
        """Test verification fails on timeout."""
        mock_run = MagicMock()
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="/usr/bin/wg", timeout=5)
        with patch('subprocess.run', mock_run):
            result = verify_wireguard_binary("/usr/bin/wg")
            assert result is False

    def test_verify_file_not_found(self):
        """Test verification fails when file not found."""
        mock_run = MagicMock()
        mock_run.side_effect = subprocess.SubprocessError("/usr/bin/wg")
        with patch('subprocess.run', mock_run):
            result = verify_wireguard_binary("/usr/bin/wg")
            assert result is False

    def test_verify_subprocess_error(self):
        """Test verification fails on subprocess error."""
        mock_run = MagicMock()
        mock_run.side_effect = subprocess.SubprocessError("/usr/bin/wg")
        with patch('subprocess.run', mock_run):
            result = verify_wireguard_binary("/usr/bin/wg")
            assert result is False

    def test_verify_non_wg_binary(self):
        """Test verification returns False for non-WG binary."""
        # Non-wg binary doesn't run subprocess, just checks file and exec
        # If it passes file and exec checks, it still returns False at the end
        with patch('os.path.isfile', return_value=True):
            with patch('os.access', return_value=True):
                result = verify_wireguard_binary("/usr/bin/notwg")
                assert result is False


class TestGetWireguardPaths:
    """Tests for get_wireguard_paths function."""

    def test_get_wireguard_paths_not_found(self):
        """Test when wg binary is not found."""
        with patch('app.utils.wireguard_detect.detect_wireguard_binaries') as mock_detect:
            mock_detect.return_value = {'wg': None}
            with patch('os.path.isfile', return_value=False):
                with patch('os.access', return_value=False):
                    result = get_wireguard_paths()
                    assert result == {'wg': '/usr/bin/wg'}

    def test_get_wireguard_paths_found(self):
        """Test when wg binary is found."""
        with patch('app.utils.wireguard_detect.detect_wireguard_binaries') as mock_detect:
            mock_detect.return_value = {'wg': '/usr/local/bin/wg'}
            with patch('os.path.isfile', return_value=True):
                with patch('os.access', return_value=True):
                    result = get_wireguard_paths()
                    assert result == {'wg': '/usr/local/bin/wg'}

    def test_get_wireguard_paths_defaults(self):
        """Test default fallback paths."""
        with patch('app.utils.wireguard_detect.detect_wireguard_binaries') as mock_detect:
            mock_detect.return_value = {'wg': None}
            with patch('os.path.isfile', return_value=False):
                with patch('os.access', return_value=False):
                    result = get_wireguard_paths()
                    assert result == {'wg': '/usr/bin/wg'}
