from web.controller import Controller


class Login(Controller):
    template = "login.html"


if __name__ == "__main__":
    Login().load()
