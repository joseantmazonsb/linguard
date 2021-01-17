from flask import Flask

from core.wireguard.server import Server
from web.router import router
import logging

from web.static.assets.resources import app_name

app = Flask(__name__, template_folder="templates")
app.register_blueprint(router)
logging.basicConfig(level=logging.DEBUG)


FILES_PATH = f"/srv/{app_name.lower()}"

if __name__ == '__main__':
    server_folder = app_name.lower()
    wg = Server(server_folder)
    wg.start()
    server_port = 5000
    app.run(debug=True, port=server_port)
