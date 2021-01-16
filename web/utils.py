from datetime import datetime
from typing import Any

from flask import templating
from web.static.assets.resources import app_name


def render_template(template_path: str, **variables: Any):
    context = {
        "app_name": app_name,
        "year": datetime.now().strftime("%Y")
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)
