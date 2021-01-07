from flask import Flask
from web.router import router
import logging

app = Flask(__name__, template_folder="templates")
app.register_blueprint(router)
logging.basicConfig(level=logging.DEBUG)


if __name__ == '__main__':
    server_port = 5000
    app.run(debug=True, port=server_port)
