import os.path

import pytest

from linguard.common.utils.system import Command
from linguard.core.config.version import version_info, VersionInfo

version_file = os.path.join(os.path.dirname(__file__), "version.yaml")


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(version_file):
        os.remove(version_file)


@pytest.fixture()
def actual_version_info():
    info = VersionInfo()
    info.commit = Command("git rev-parse HEAD").run().output
    assert info.commit
    info.release = Command("poetry version -s").run().output
    assert info.release
    info.dump_yaml(version_file)
    yield info


class TestVersion:

    def test_version_info_ok(self, actual_version_info):
        version_info.load(version_file)
        assert version_info.release == actual_version_info.release
        assert version_info.commit == actual_version_info.commit
