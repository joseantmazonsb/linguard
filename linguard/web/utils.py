from datetime import datetime
from typing import Any

import faker
from flask import templating

from linguard.__version__ import commit, release
from linguard.common.properties import global_properties
from linguard.web.static.assets.resources import APP_NAME

fake = faker.Faker()


def render_template(template_path: str, **variables: Any):
    context = {
        "app_name": APP_NAME,
        "year": datetime.now().strftime("%Y"),
        "version_info": {"release": release, "commit": commit},
        "dev_env": global_properties.dev_env
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)
