from web.static.assets.resources import APP_NAME


class WireguardError(Exception):
    def __init__(self, cause: str):
        if "sudo" in cause:
            self.cause = f"unable to perform an operation which requires root permissions. " \
                         f"Make sure {APP_NAME}'s permissions are correctly set."
        else:
            self.cause = cause
        super()

    def __str__(self):
        return self.cause
