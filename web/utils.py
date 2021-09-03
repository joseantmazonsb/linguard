from datetime import datetime
from typing import Any

import faker
from flask import templating

from web.static.assets.resources import APP_NAME

fake = faker.Faker()


def render_template(template_path: str, **variables: Any):
    context = {
        "app_name": APP_NAME,
        "year": datetime.now().strftime("%Y")
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)
