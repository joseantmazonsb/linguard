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
    wg.add_interface("scranton-vpn", "10.0.100.1/24", "VPN for Scranton branch")
    wg.add_interface("ny-vpn", "10.0.101.1/24", "VPN for NY branch")
    wg.add_client(name="jim", interface="scranton-vpn", dns1="8.8.8.8", ipv4_address="10.0.100.2/24")
    wg.add_client(name="michael", interface="scranton-vpn", dns1="8.8.8.8", ipv4_address="10.0.100.3/24")
    wg.add_client(name="karen", interface="ny-vpn", dns1="8.8.8.8", ipv4_address="10.0.101.2/24")
    router.server = wg
    wg.start()
    server_port = 5000
    app.run(debug=False, port=server_port)
