import argparse
import atexit
import os
from logging import warning, fatal, info, debug

from flask import Flask
from flask_login import LoginManager
from flask_qrcode import QRcode

from linguard.__version__ import commit, release
from linguard.common.models.user import users
from linguard.common.properties import global_properties
from linguard.common.utils.system import try_makedir
from linguard.core.managers.cron import cron_manager
from linguard.core.managers.wireguard import wireguard_manager
from linguard.web.static.assets.resources import APP_NAME

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id, None)


def parse_args():
    parser = argparse.ArgumentParser(description=f"Welcome to {APP_NAME}, the best WireGuard's web GUI :)")
    parser.add_argument("workdir", type=str,
                        help=f"Path to the directory used to store all data related to {APP_NAME}.")
    parser.add_argument("--debug", help="Start flask in debug mode.", action="store_true")
    return parser.parse_args()


args = parse_args()

workdir = os.path.abspath(args.workdir)
if os.path.exists(workdir) and not os.path.isdir(workdir):
    fatal(f"'{workdir}' is not a valid working directory!")
try_makedir(workdir)
global_properties.workdir = workdir

from linguard.core.config.web import config as web_config
from linguard.core.config.logger import config as log_config
from linguard.core.managers.config import config_manager
from linguard.web.router import router

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
info(f"Logging to '{log_config.logfile}'...")
config_manager.load()
if log_config.overwrite:
    log_config.reset_logfile()

app.config['SECRET_KEY'] = web_config.secret_key
app.register_blueprint(router)
QRcode(app)
login_manager.init_app(app)
wireguard_manager.start()
cron_manager.start()


@atexit.register
def on_exit():
    warning(f"Shutting down {APP_NAME}...")
    cron_manager.stop()
    wireguard_manager.stop()


if __name__ == "__main__":
    warning("**************************")
    warning("RUNNING DEVELOPMENT SERVER")
    warning("**************************")
    global_properties.dev_env = True
    # Override log level (although it can be manually edited via UI)
    log_config.level = "debug"
    log_config.apply()
    # Unlike the production scenario, a missing version file is not fatal
    if not release or not commit:
        warning("!! No versioning information provided !!")
    else:
        info(f"Running {APP_NAME} {release}")
        debug(f"Commit hash: {commit}")
    app.run(debug=args.debug, port=8080)
else:
    if not release or not commit:
        if global_properties.dev_env:
            warning("!! No versioning information provided !!")
        else:
            fatal("!! No versioning information provided !!")
            exit(1)
    if "-" or "+" in release:
        global_properties.dev_env = True
    info(f"Running {APP_NAME} {release}")
    debug(f"Commit hash: {commit}")
