from typing import Dict, Any

from flask import Response

from core.wireguard.server import Server


class RestController:
    def __init__(self, server: Server, data: Dict[str, Any]):
        self.server = server
        self.data = data

    def serve(self) -> Response:
        pass
