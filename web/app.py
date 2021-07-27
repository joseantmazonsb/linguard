import argparse
import logging
import os

from flask import Flask

from core.modules.config import Config
from core.server import Server
from web.router import router

from web.static.assets.resources import APP_NAME


parser = argparse.ArgumentParser(description="Welcome to Linguard, the best WireGuard's web GUI :)")
parser.add_argument("config", type=str, help="Path to the configuration file.")
parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")
args = parser.parse_args()


def start():
    logging.basicConfig(format=Config.LOG_FORMAT, level=Config.DEFAULT_LEVEL)
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(router)
    wg = Server(os.path.abspath(args.config))
    router.server = wg
    wg.start()
    app.run(debug=args.debug, port=wg.config.web()["bindport"])


start()
