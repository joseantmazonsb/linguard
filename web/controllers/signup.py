from web.controller import Controller


class Signup(Controller):
    template = "register.html"


if __name__ == "__main__":
    Signup().load()
