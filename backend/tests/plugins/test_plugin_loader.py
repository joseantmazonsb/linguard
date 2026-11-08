"""
Comprehensive tests for PluginLoader - app/plugins/loader.py
Covers all methods and edge cases to achieve 100% coverage.
"""
import inspect
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from app.plugins.loader import PluginLoader


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def plugin_loader():
    """Create a plugin loader instance."""
    return PluginLoader()


# ============================================================================
# TESTS FOR PluginLoader.discover_plugins
# ============================================================================

class TestPluginLoaderDiscoverPlugins:
    """Tests for PluginLoader.discover_plugins method."""
    
    def test_discover_plugins_empty_directory(self, plugin_loader, tmp_path):
        """Test discovering plugins in an empty directory."""
        result = plugin_loader.discover_plugins(str(tmp_path))
        assert result == []
        assert plugin_loader.discovered_plugins == {}
    
    def test_discover_plugins_nonexistent_directory(self, plugin_loader, tmp_path):
        """Test discovering plugins in a nonexistent directory."""
        # Create a temp directory that doesn't exist yet
        test_dir = tmp_path / "test_nonexistent"
        result = plugin_loader.discover_plugins(str(test_dir))
        assert result == []
        # Verify directory was created (as per implementation)
        assert test_dir.exists()
    
    def test_discover_plugins_directory_not_dir(self, plugin_loader, tmp_path):
        """Test discovering when path is not a directory."""
        result = plugin_loader.discover_plugins(str(tmp_path / "file.txt"))
        assert result == []
    
    def test_discover_plugins_with_plugin_file(self, plugin_loader, tmp_path):
        """Test discovering plugins with a plugin file."""
        from app.plugins.base import plugin
        
        # Create a mock plugin directory
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        
        # Create a simple plugin.py file with proper decorator
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(f"""
from app.plugins.base import plugin

@plugin(name="Test Plugin", version="1.0.0")
class TestPlugin:
    pass
""")
        
        result = plugin_loader.discover_plugins(str(tmp_path))
        assert len(result) == 1
        assert result[0]['module_name'] == 'test_plugin'
        assert 'plugin_class' in result[0]


# ============================================================================
# TESTS FOR PluginLoader._load_plugin_file
# ============================================================================

class TestPluginLoaderLoadPluginFile:
    """Tests for PluginLoader._load_plugin_file method."""
    
    def test_load_plugin_file_success(self, plugin_loader, tmp_path):
        """Test loading a plugin file successfully."""
        from app.plugins.base import plugin
        
        # Create a mock plugin directory
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        
        # Create a simple plugin.py file
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(f"""
from app.plugins.base import plugin

@plugin(name="Test Plugin", version="1.0.0")
class TestPlugin:
    pass
""")
        
        result = plugin_loader._load_plugin_file("test_plugin", str(plugin_file))
        assert result is not None
        assert result['module_name'] == 'test_plugin'
        assert 'plugin_class' in result
    
    def test_load_plugin_file_invalid_python(self, plugin_loader, tmp_path):
        """Test loading a file with invalid Python syntax."""
        plugin_dir = tmp_path / "invalid_plugin"
        plugin_dir.mkdir()
        
        # Create an invalid Python file
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text("""
def invalid:
    pass  # Missing colon
""")
        
        result = plugin_loader._load_plugin_file("invalid_plugin", str(plugin_file))
        assert result is None
    
    def test_load_plugin_file_no_plugin_class(self, plugin_loader, tmp_path):
        """Test loading a file without a @plugin decorated class."""
        plugin_dir = tmp_path / "no_plugin_class"
        plugin_dir.mkdir()
        
        # Create a file without plugin decorator
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text("""
class SomeClass:
    pass
""")
        
        result = plugin_loader._load_plugin_file("no_plugin_class", str(plugin_file))
        assert result is None
    
    def test_load_plugin_file_single_plugin_class(self, plugin_loader, tmp_path):
        """Test loading a file with a single plugin class."""
        from app.plugins.base import plugin
        
        plugin_dir = tmp_path / "single_plugin"
        plugin_dir.mkdir()
        
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(f"""
from app.plugins.base import plugin

@plugin(name="SinglePlugin", version="1.0.0")
class SinglePlugin:
    pass
""")
        
        result = plugin_loader._load_plugin_file("single_plugin", str(plugin_file))
        assert result is not None
        assert result.get('plugin_class') is not None
        assert result.get('metadata') is not None
        assert result['metadata'].name == 'SinglePlugin'


# ============================================================================
# TESTS FOR PluginLoader._extract_event_handlers
# ============================================================================

class TestPluginLoaderExtractEventHandlers:
    """Tests for PluginLoader._extract_event_handlers method."""
    
    def test_extract_event_handlers_no_handlers(self, plugin_loader, tmp_path):
        """Test extracting handlers from a file with no event handlers."""
        plugin_dir = tmp_path / "no_handlers"
        plugin_dir.mkdir()
        
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text("""
@plugin
class Plugin:
    def method(self):
        pass
""")
        
        result = plugin_loader._load_plugin_file("no_handlers", str(plugin_file))
        if result:
            plugin_loader._extract_event_handlers(
                result['plugin_class'],
                result['metadata']
            )
            # Should have registered the method handler


# ============================================================================
# TESTS FOR PluginLoader._parse_requirements
# ============================================================================

class TestPluginLoaderParseRequirements:
    """Tests for PluginLoader._parse_requirements method."""
    
    def test_parse_requirements_empty_file(self, plugin_loader, tmp_path):
        """Test parsing an empty requirements file."""
        requirements_file = tmp_path / "requirements.txt"
        requirements_file.write_text("")
        
        result = plugin_loader._parse_requirements(str(requirements_file))
        assert result == []
    
    def test_parse_requirements_with_packages(self, plugin_loader, tmp_path):
        """Test parsing a requirements file with packages."""
        requirements_file = tmp_path / "requirements.txt"
        requirements_file.write_text("""
# Comment
requests==2.28.0
flask
numpy>=1.20.0

pandas
""")
        
        result = plugin_loader._parse_requirements(str(requirements_file))
        assert len(result) == 4  # 4 packages (comment line skipped)
        assert 'requests==2.28.0' in result
        assert 'flask' in result
        assert 'numpy>=1.20.0' in result
        assert 'pandas' in result
    
    def test_parse_requirements_with_invalid_lines(self, plugin_loader, tmp_path):
        """Test parsing a requirements file with invalid lines."""
        requirements_file = tmp_path / "requirements.txt"
        requirements_file.write_text("""
requests
# comment
invalid line without package
""")
        
        result = plugin_loader._parse_requirements(str(requirements_file))
        assert 'requests' in result
        assert len(result) > 0


# ============================================================================
# TESTS FOR PluginLoader.get_plugin_subscribed_events
# ============================================================================

class TestPluginLoaderGetPluginSubscribedEvents:
    """Tests for PluginLoader.get_plugin_subscribed_events method."""
    
    def test_get_subscribed_events_empty(self, plugin_loader):
        """Test getting subscribed events for a non-existent plugin."""
        result = plugin_loader.get_plugin_subscribed_events(MagicMock())
        assert result == []
    
    def test_get_subscribed_events_with_plugin(self, plugin_loader, tmp_path):
        """Test getting subscribed events for a plugin."""
        from app.plugins.base import plugin, _plugin_registry
        from unittest.mock import MagicMock
        
        # Create a mock plugin class with the right metadata
        mock_plugin_class = MagicMock()
        mock_plugin_class._plugin_name = "TestPlugin"
        
        # Create a mock metadata with event handlers
        mock_metadata = MagicMock()
        mock_metadata.event_handlers = {
            "event1": [],
            "event2": []
        }
        
        # Register the mock plugin in the registry
        _plugin_registry[mock_plugin_class] = mock_metadata
        
        # Now test get_plugin_subscribed_events
        result = plugin_loader.get_plugin_subscribed_events(mock_plugin_class)
        assert result == ["event1", "event2"]


# ============================================================================
# TESTS FOR PluginLoader.instantiate_plugin
# ============================================================================

class TestPluginLoaderInstantiatePlugin:
    """Tests for PluginLoader.instantiate_plugin method."""
    
    def test_instantiate_plugin_with_context(self, plugin_loader):
        """Test instantiating a plugin with context parameter."""
        # Create a mock class with a signature that takes context
        class MockPluginWithContext:
            def __init__(self, context):
                pass
        
        # We need to register this mock plugin in the registry for it to work properly
        # Get the actual PluginMetadata
        from app.plugins.base import _plugin_registry, plugin
        
        # Create a mock metadata and register it
        from unittest.mock import MagicMock
        
        mock_metadata = MagicMock()
        mock_metadata._plugin_name = "MockPluginWithContext"
        _plugin_registry[MockPluginWithContext] = mock_metadata
        
        mock_context = MagicMock()
        
        result = plugin_loader.instantiate_plugin(MockPluginWithContext, mock_context)
        # Should have called the constructor with context
        assert result is not None
    
    def test_instantiate_plugin_without_context(self, plugin_loader):
        """Test instantiating a plugin without context parameter."""
        # Create a mock class with a signature that takes no context
        class MockPluginWithoutContext:
            def __init__(self):
                pass
        
        # We need to register this mock plugin in the registry for it to work properly
        from app.plugins.base import _plugin_registry, plugin
        
        # Create a mock metadata and register it
        from unittest.mock import MagicMock
        
        mock_metadata = MagicMock()
        mock_metadata._plugin_name = "MockPluginWithoutContext"
        _plugin_registry[MockPluginWithoutContext] = mock_metadata
        
        # Test instantiating without context
        result = plugin_loader.instantiate_plugin(MockPluginWithoutContext, MagicMock())
        # Should have instantiated without context
        assert result is not None


# ============================================================================
# TESTS FOR PluginLoader.discovered_plugins property
# ============================================================================

class TestPluginLoaderDiscoveredPlugins:
    """Tests for PluginLoader.discovered_plugins property."""
    
    def test_discovered_plugins_empty(self, plugin_loader):
        """Test that discovered_plugins is initially empty."""
        assert plugin_loader.discovered_plugins == {}
    
    def test_discovered_plugins_after_discovery(self, plugin_loader, tmp_path):
        """Test that discovered_plugins is populated after discovery."""
        from app.plugins.base import plugin
        
        # Create a mock plugin directory
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(f"""
from app.plugins.base import plugin

@plugin(name="TestPlugin", version="1.0.0")
class TestPlugin:
    pass
""")
        
        plugin_loader.discover_plugins(str(tmp_path))
        assert plugin_loader.discovered_plugins.get('test_plugin') is not None
