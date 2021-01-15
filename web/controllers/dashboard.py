from web.controller import Controller


class Dashboard(Controller):
    template = "index.html"
    context = {
        "title": "Dashboard"
    }


if __name__ == "__main__":
    Dashboard().load()
