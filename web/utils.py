from flask import templating
from web.static.assets.resources import app_name


def render_template(template_path: str):
    return templating.render_template(template_path, app_name=app_name)
