import logging
import sys

from flask import Flask

from core.modules.config import Config
from core.server import Server
from web.router import router

from web.static.assets.resources import APP_NAME


def start(debug: bool = False):
    logging.basicConfig(format=Config.LOG_FORMAT, level=Config.DEFAULT_LEVEL)
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(router)
    conf_dir = APP_NAME.lower()
    if len(sys.argv) > 1:
        conf_dir = sys.argv[1]
    wg = Server(conf_dir)
    router.server = wg
    wg.start()
    app.run(debug=False, port=wg.config.web()["bindport"])


if __name__ == '__main__':
    start(True)
else:
    start()
