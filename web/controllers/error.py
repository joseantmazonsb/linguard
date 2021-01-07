from web.controller import Controller


class NotFound(Controller):
    template = "error/404.html"


class InternalServerError(Controller):
    template = "error/500.html"


class Unauthorized(Controller):
    template = "error/401.html"
