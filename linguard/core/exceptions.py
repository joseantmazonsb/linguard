from http.client import INTERNAL_SERVER_ERROR

from linguard.web.static.assets.resources import APP_NAME


class WireguardError(Exception):
    def __init__(self, cause: str, http_code: int = INTERNAL_SERVER_ERROR):
        self.http_code = http_code
        if "sudo" in cause:
            self.cause = f"unable to perform an operation which requires root permissions. " \
                         f"Make sure {APP_NAME}'s permissions are correctly set."
            self.http_code = 500
        else:
            self.cause = cause
        super()

    def __str__(self):
        return self.cause
