from typing import Any

from linguard.web.utils import render_template


class ViewController:

    def __init__(self, template: str, **context: Any):
        self.template = template
        self.context = context

    def load(self):
        self.view = render_template(self.template, **self.context)
        return self.view
