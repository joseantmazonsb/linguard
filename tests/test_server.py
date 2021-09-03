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

    @pytest.mark.skipif(os.environ.get("skip_sample_server", None),
                        reason="This test may fail due to permission issues.")
    def test_sample_server(self):
        server = Server("../config/linguard.sample.yaml")
        server.start()
        server.stop()
