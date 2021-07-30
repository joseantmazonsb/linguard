import argparse
import logging
import os

import flask
from flask import Flask

from core.app_manager import AppManager, manager
from core.wireguard import LoggerOptions, config
from web.router import router


class Server:
    app: flask.app
    app_manager: AppManager

    @property
    def bindport(self):
        return config.web_options.bindport

    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Welcome to Linguard, the best WireGuard's web GUI :)")
        self.parser.add_argument("config", type=str, help="Path to the configuration file.")
        self.parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")

        self.args = self.parser.parse_args()

        logging.basicConfig(format=LoggerOptions.LOG_FORMAT, level=LoggerOptions.DEFAULT_LEVEL)
        self.app_manager = manager
        self.app_manager.initialize(os.path.abspath(self.args.config))
        self.app = Flask(__name__, template_folder="templates")
        self.app.register_blueprint(router)

    def run(self):
        logging.info(f"Running backend...")
        self.app.run(debug=self.args.debug, port=self.bindport)


server = Server()
server.run()
