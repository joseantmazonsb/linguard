from typing import Any, Dict

from flask import templating
from web.static.assets.resources import app_name


def render_template(template_path: str, variables: Dict[str, Any] = None):
    context = {
        "app_name": app_name
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)
