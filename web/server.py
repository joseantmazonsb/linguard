import logging

import flask
from flask import Flask
from flask_login import LoginManager

from core.config.linguard_config import config
from core.config.web_config import config as web_config
from core.config_manager import ConfigManager, config_manager
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

    def __init__(self, config_file: str, debug: bool = False):
        self.config_manager = config_manager
        self.config_manager.load(config_file)
        self.app = Flask(__name__, template_folder="templates")
        self.app.config['SECRET_KEY'] = web_config.secret_key
        self.app.register_blueprint(router)
        self.debug = debug
        self.started = False
        login_manager.init_app(self.app)

    def start(self):
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

    def run(self):
        self.start()
        logging.info("Running backend...")
        self.app.run(debug=self.debug, port=self.bindport, host=self.host)
