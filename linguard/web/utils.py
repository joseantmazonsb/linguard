from datetime import datetime
from typing import Any

import faker
from flask import templating

from linguard.core.config.version import version_info
from linguard.core.managers.config import GLOBAL_PROPERTIES
from linguard.web.static.assets.resources import APP_NAME

fake = faker.Faker()


def render_template(template_path: str, **variables: Any):
    context = {
        "app_name": APP_NAME,
        "year": datetime.now().strftime("%Y"),
        "version_info": version_info,
        "dev_env": GLOBAL_PROPERTIES["dev_env"]
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)
