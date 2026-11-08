"""
Minimal tests for WireGuardService to achieve high coverage.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.wireguard import WireGuardService
from app.services.firewall.service import FirewallService


class TestWireGuardServiceMinimal:
    """Minimal test suite for WireGuardService."""

    @pytest.fixture
    def test_wireguard_service(self):
        """Create a WireGuardService with mocked firewall."""
        with patch('app.services.firewall.service.FirewallService', return_value=MagicMock()):
            service = WireGuardService(wg_binary="wg-test")
            return service

    def test_generate_keypair_success(self, test_wireguard_service):
        """Test successful key pair generation."""
        from subprocess import CompletedProcess
        
        # Create proper mock CompletedProcess objects
        mock_private_result = MagicMock(spec=CompletedProcess)
        mock_private_result.stdout = "test_private_key"
        mock_private_result.returncode = 0
        
        mock_public_result = MagicMock(spec=CompletedProcess)
        mock_public_result.stdout = "test_public_key"
        mock_public_result.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', side_effect=[mock_private_result, mock_public_result]):
            private_key, public_key = test_wireguard_service.generate_keypair()
            
            assert private_key == "test_private_key"
            assert public_key == "test_public_key"

    def test_generate_preshared_key(self):
        """Test preshared key generation."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "test_preshared_key"
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            key = service.generate_preshared_key()
            
            assert isinstance(key, str)
            assert len(key) > 0

    def test_derive_public_key(self):
        """Test public key derivation from private key."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "test_public_key"
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            # Private key must be exactly 44 chars including '='
            private_key = "8EgEJ5kAw+YSVemUSLUeeShrq95QifM1VHGQrcLNmWk="
            public_key = service.derive_public_key(private_key)
            
            assert isinstance(public_key, str)
            assert len(public_key) > 0

    def test_generate_config_file_empty(self):
        """Test generating empty config file."""
        service = WireGuardService(wg_binary="wg-test")
        
        result = service.generate_config_file(
            interface="wg0",
            private_key="private_key",
            address="10.0.0.1/32",
            listen_port=51820,
            peers=[]
        )
        
        assert isinstance(result, str)
        assert "PrivateKey" in result

    def test_generate_config_file_with_data(self):
        """Test generating config file with data."""
        service = WireGuardService(wg_binary="wg-test")
        
        config = service.generate_config_file(
            interface="wg0",
            private_key="private_key",
            address="10.0.0.1/32",
            listen_port=51820,
            peers=[]
        )
        
        assert isinstance(config, str)
        assert "PrivateKey" in config
        assert "ListenPort" in config

    def test_generate_peer_config_empty(self):
        """Test generating empty peer config."""
        service = WireGuardService(wg_binary="wg-test")
        
        result = service.generate_peer_config(
            private_key="private_key",
            address="10.0.0.1/32",
            dns=None,
            server_public_key="server_public_key",
            server_endpoint="server:51820",
            server_port=51820,
            allowed_ips="0.0.0.0/0, ::/0",
            persistent_keepalive=25,
            preshared_key=None
        )
        
        assert isinstance(result, str)

    def test_generate_peer_config_with_data(self):
        """Test generating peer config with data."""
        service = WireGuardService(wg_binary="wg-test")
        
        config = service.generate_peer_config(
            private_key="private_key",
            address="10.0.0.1/32",
            dns=None,
            server_public_key="server_public_key",
            server_endpoint="server:51820",
            server_port=51820,
            allowed_ips="0.0.0.0/0, ::/0",
            persistent_keepalive=25,
            preshared_key=None
        )
        
        assert isinstance(config, str)

    def test_run_sudo_command_non_interactive(self):
        """Test sudo command with -n flag."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "test_output"
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._run_sudo_command(
                cmd=["sudo", "test", "command"],
                input_data=None
            )
            
            assert result.returncode == 0

    def test_run_sudo_command_with_input(self):
        """Test sudo command with input data."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "test_output"
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._run_sudo_command(
                cmd=["sudo", "echo", "test"],
                input_data="hello"
            )
            
            assert result.returncode == 0

    def test_run_sudo_command_macos_non_interactive(self):
        """Test sudo command on macOS without password."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "test_output"
        mock.returncode = 1
        
        with patch('platform.system', return_value='Darwin'):
            with patch('app.services.firewall.service.FirewallService'):
                with patch('app.services.wireguard.subprocess.run', return_value=mock):
                    service = WireGuardService(wg_binary="wg-test")
                      
                    result = service._run_sudo_command(
                        cmd=["sudo", "test", "command"],
                        input_data=None
                    )
                      
                    assert result.returncode != 0

    def test_get_next_available_interface(self):
        """Test getting next available interface name."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.get_next_available_interface()
            
            assert result is not None

    def test_get_all_interfaces_empty(self):
        """Test getting all interfaces when none exist."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.get_all_interfaces()
            
            assert isinstance(result, list)
            assert len(result) == 0

    def test_get_all_interfaces_with_interfaces(self, test_wireguard_service):
        """Test getting all interfaces."""
        from subprocess import CompletedProcess
        
        mock_ip_output = "<POINTOPOINT,NOARP,UP,LOWER_UP>"
        mock_stdout = """interface: wg0
public key: test_public_key_0123456789012345678901234567890123456789012345678901234567890123
""".strip()
        
        # Handle firewall service subprocess calls (iptables_driver uses subprocess)
        def make_firewall_mock(*args):
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = ""
            mock.returncode = 0
            result = MagicMock()
            result.stdout = ""
            return mock
        
        # Create mocks for wg show all and ip link show
        def make_wg_mock():
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = mock_stdout
            mock.returncode = 0
            wg_result = MagicMock(spec=CompletedProcess)
            wg_result.stdout = mock_stdout
            return mock
        
        def make_ip_mock():
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = mock_ip_output
            mock.returncode = 0
            ip_result = MagicMock(spec=CompletedProcess)
            ip_result.stdout = mock_ip_output
            return mock
        
        with patch('app.services.firewall.iptables_driver.subprocess.run', side_effect=[
            make_firewall_mock(), make_firewall_mock()
        ]):
            with patch('app.services.wireguard.subprocess.run', side_effect=[
                make_wg_mock(), make_ip_mock()
            ]):
                result = test_wireguard_service.get_all_interfaces()
                
                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0]["interface"] == "wg0"
                assert result[0]["public_key"] == "test_public_key_0123456789012345678901234567890123456789012345678901234567890123"

    def test_find_interface_by_public_key_empty(self):
        """Test finding interface by public key when not found."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.find_interface_by_public_key("nonexistent_key")
            
            assert result is None

    def test_find_interface_by_public_key_found(self, test_wireguard_service):
        """Test finding interface by public key."""
        from subprocess import CompletedProcess
        
        mock_ip_output = "<POINTOPOINT,NOARP,UP,LOWER_UP>"
        mock_stdout = """interface: wg0
public key: test_public_key
""".strip()
        
        # Handle firewall service subprocess calls (iptables_driver uses subprocess)
        def make_firewall_mock(*args):
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = ""
            mock.returncode = 0
            result = MagicMock()
            result.stdout = ""
            return mock
        
        # Create mocks for wg show all and ip link show
        def make_wg_mock():
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = mock_stdout
            mock.returncode = 0
            wg_result = MagicMock(spec=CompletedProcess)
            wg_result.stdout = mock_stdout
            return mock
        
        def make_ip_mock():
            mock = MagicMock(spec=CompletedProcess)
            mock.stdout = mock_ip_output
            mock.returncode = 0
            ip_result = MagicMock(spec=CompletedProcess)
            ip_result.stdout = mock_ip_output
            return mock
        
        with patch('app.services.firewall.iptables_driver.subprocess.run', side_effect=[
            make_firewall_mock(), make_firewall_mock()
        ]):
            with patch('app.services.wireguard.subprocess.run', side_effect=[
                make_wg_mock(), make_ip_mock()
            ]):
                result = test_wireguard_service.find_interface_by_public_key("test_public_key")
                
                assert result is not None
                assert result == "wg0"

    def test_bring_interface_up_success(self):
        """Test bringing interface up successfully."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._bring_interface_up("wg0")
            
            assert result is True

    def test_bring_interface_up_failure(self):
        """Test bringing interface up fails."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 1
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._bring_interface_up("wg0")
            
            assert result is False

    def test_stop_interface_success(self):
        """Test stopping interface successfully."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.stop_interface("wg0")
            
            assert result is True

    def test_stop_interface_failure(self):
        """Test stopping interface fails."""
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "error: interface not found"
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.stop_interface("wg0")
            
            assert result is False

    def test_get_interface_status_up(self):
        """Test getting interface status when up."""
        mock = MagicMock()
        mock.stdout.strip.return_value = "interface: wg0"
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.get_interface_status("wg0")
            
            assert result is not None
            assert result["status"] == "running"

    def test_get_interface_status_down(self):
        """Test getting interface status when down."""
        mock = MagicMock()
        mock.returncode = 1
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service.get_interface_status("wg0")
            
            assert result is not None
            assert result["status"] == "stopped"

    def test_is_interface_up_true(self):
        """Test checking if interface is up."""
        mock_stdout = "<POINTOPOINT,NOARP,UP,LOWER_UP>"
        mock = MagicMock()
        mock.stdout = mock_stdout
        mock.returncode = 0
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._is_interface_up("wg0")
            
            assert result is True

    def test_is_interface_up_false(self):
        """Test checking if interface is down."""
        mock = MagicMock()
        mock.stdout.strip.return_value = ""
        mock.returncode = 1
        
        with patch('app.services.wireguard.subprocess.run', return_value=mock):
            service = WireGuardService(wg_binary="wg-test")
            
            result = service._is_interface_up("wg0")
            
            assert result is False

    def test_get_config_file_with_peers(self):
        """Test generating config file with peers."""
        service = WireGuardService(wg_binary="wg-test")
        
        config = service.generate_config_file(
            interface="wg0",
            private_key="private_key",
            address="10.0.0.1/32",
            listen_port=51820,
            peers=[{"public_key": "peer_key"}]
        )
        
        assert isinstance(config, str)
        assert "PublicKey" in config

    def test_get_peer_config_with_all_options(self):
        """Test generating peer config with all options."""
        service = WireGuardService(wg_binary="wg-test")
        
        config = service.generate_peer_config(
            private_key="private_key",
            address="10.0.0.1/32",
            dns="8.8.8.8",
            server_public_key="server_public_key",
            server_endpoint="server:51820",
            server_port=51820,
            allowed_ips="0.0.0.0/0, ::/0",
            persistent_keepalive=25,
            preshared_key="preshared"
        )
        
        assert isinstance(config, str)
        assert "server:51820" in config
        assert "8.8.8.8" in config
        assert "PresharedKey" in config
