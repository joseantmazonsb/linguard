import argparse
import logging
import os

import flask
from flask import Flask
from flask_login import LoginManager

from core.config.linguard_config import config
from core.config_manager import ConfigManager, config_manager
from core.config.web_config import config as web_config
from core.exceptions import WireguardError
from web.models import users
from web.router import router

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id, None)


class Server:
    app: flask.app
    config_manager: ConfigManager

    @property
    def bindport(self):
        return web_config.bindport

    @property
    def host(self):
        return web_config.host

    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Welcome to Linguard, the best WireGuard's web GUI :)")
        self.parser.add_argument("config", type=str, help="Path to the configuration file.")
        self.parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")

        self.args = self.parser.parse_args()

        self.config_manager = config_manager
        self.config_manager.load(os.path.abspath(self.args.config))
        self.app = Flask(__name__, template_folder="templates")
        self.app.config['SECRET_KEY'] = web_config.secret_key
        self.app.register_blueprint(router)
        self.started = False
        login_manager.init_app(self.app)

    def run(self):
        logging.info("Starting VPN server...")
        if self.started:
            logging.warning("Unable to start VPN server: already started.")
            return
        for iface in config.interfaces.values():
            if not iface.auto:
                continue
            try:
                iface.up()
            except WireguardError:
                pass
        self.started = True
        logging.info("VPN server started.")
        logging.info("Running backend...")
        self.app.run(debug=self.args.debug, port=self.bindport, host=self.host)

    def stop(self):
        logging.info("Stopping VPN server...")
        if not self.started:
            logging.warning("Unable to stop VPN server: already stopped.")
            return
        for iface in config.interfaces.values():
            try:
                iface.down()
            except WireguardError:
                pass
        self.started = False
        logging.info("VPN server stopped.")


server = Server()
server.run()
