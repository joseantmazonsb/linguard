from flask import Flask

from core.wireguard import Server
from web.router import router
import logging

from web.static.assets.resources import app_name

app = Flask(__name__, template_folder="templates")
app.register_blueprint(router)
logging.basicConfig(level=logging.DEBUG)


FILES_PATH = f"/srv/{app_name.lower()}"

if __name__ == '__main__':
    wg = Server("wlan0", FILES_PATH, "wg", "wg-quick", "iptables")
    wg.start()
    server_port = 5000
    app.run(debug=True, port=server_port)
