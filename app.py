import argparse
import os
from logging import warning

from flask import Flask
from flask_login import LoginManager

from core.config.web_config import config
from core.config_manager import config_manager
from core.wireguard_manager import wireguard_manager
from web.models import users
from web.router import router

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id, None)


parser = argparse.ArgumentParser(description="Welcome to Linguard, the best WireGuard's web GUI :)")
parser.add_argument("config", type=str, help="Path to the configuration file.")
parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")
args = parser.parse_args()

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
config_manager.load(os.path.abspath(args.config))
app.config['SECRET_KEY'] = config.secret_key
app.register_blueprint(router)
login_manager.init_app(app)
wireguard_manager.start()

if __name__ == "__main__":
    warning("Running development server...")
    app.run(debug=args.debug, port=8080)
