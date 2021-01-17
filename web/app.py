from flask import Flask

from core.wireguard.server import Server
from web.router import router
import logging

from web.static.assets.resources import app_name

if __name__ == '__main__':
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(router)
    logging.basicConfig(level=logging.DEBUG)

    FILES_PATH = f"/srv/{app_name.lower()}"

    server_folder = app_name.lower()
    wg = Server(server_folder)
    wg.add_interface("scranton-vpn", "10.0.100.1/24", "VPN for Scranton branch")
    wg.add_interface("ny-vpn", "10.0.101.1/24", "VPN for NY branch")
    router.server = wg
    wg.start()
    server_port = 5000
    app.run(debug=True, port=server_port)
