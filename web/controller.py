from web.utils import render_template


class Controller:
    template: str

    def load(self):
        self.before_render()
        self.view = render_template(self.template)
        self.after_render()
        return self.view

    def before_render(self):
        pass

    def after_render(self):
        pass
