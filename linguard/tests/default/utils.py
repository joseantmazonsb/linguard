import sys

from linguard.tests.utils import get_testing_app


def get_default_app():
    sys.argv = [sys.argv[0], "linguard.test.yaml"]
    return get_testing_app()

