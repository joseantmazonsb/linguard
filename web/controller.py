from typing import Any

from web.utils import render_template


class Controller:

    def __init__(self, template: str, **context: Any):
        self.template = template
        self.context = context

    def load(self):
        self.view = render_template(self.template, **self.context)
        return self.view
