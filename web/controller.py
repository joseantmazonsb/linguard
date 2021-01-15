from typing import Dict, Any

from web.utils import render_template


class Controller:
    template: str
    context: Dict[str, Any]

    def load(self):
        self.before_render()
        self.view = render_template(self.template, self.context)
        self.after_render()
        return self.view

    def before_render(self):
        pass

    def after_render(self):
        pass
