from flask import Flask

from core.wireguard.server import Server
from web.router import router
import logging

from web.static.assets.resources import APP_NAME

if __name__ == '__main__':
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(router)
    logging.basicConfig(level=logging.DEBUG)

    FILES_PATH = f"/srv/{APP_NAME.lower()}"

    server_folder = APP_NAME.lower()
    wg = Server(server_folder)
    router.server = wg
    wg.start()
    server_port = 5000
    app.run(debug=False, port=server_port)
