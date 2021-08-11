import argparse
import logging
import os

import flask
from flask import Flask
from flask_login import LoginManager

from core.app_manager import AppManager, manager
from core.config.web_config import config as web_config
from web.models import users
from web.router import router

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id, None)


class Server:
    app: flask.app
    app_manager: AppManager

    @property
    def bindport(self):
        return web_config.bindport

    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Welcome to Linguard, the best WireGuard's web GUI :)")
        self.parser.add_argument("config", type=str, help="Path to the configuration file.")
        self.parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")

        self.args = self.parser.parse_args()

        self.app_manager = manager
        self.app_manager.initialize(os.path.abspath(self.args.config))
        self.app = Flask(__name__, template_folder="templates")
        self.app.config['SECRET_KEY'] = web_config.secret_key
        self.app.register_blueprint(router)
        login_manager.init_app(self.app)

    def run(self):
        logging.info(f"Running backend...")
        self.app.run(debug=self.args.debug, port=self.bindport)


server = Server()
server.run()
