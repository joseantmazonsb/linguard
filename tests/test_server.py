import os

import pytest

from web.server import Server


class TestServer:

    def test_default_server(self):
        """Test with not existent configuration file, so that the app loads all default values."""
        server = Server("linguard.test.yaml")
        server.start()
        server.stop()
        os.remove(server.config_manager.config_filepath)

    @pytest.mark.skipif("skip_sample_server" in os.environ, reason="This test may fail due to permission issues.")
    def test_sample_server(self):
        path = "../config/linguard.sample.yaml"
        if "github_action_hook" in os.environ:
            path = "config/linguard.sample.yaml"
        server = Server(path)
        server.start()
        server.stop()
