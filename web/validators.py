from logging import error

from wtforms.validators import StopValidation

from core.config.web_config import config
from core.crypto_utils import CryptoUtils
from web.models import users


def stop_validation(field, error_msg):
    error(f"Unable to validate field '{field.label.text}': {error_msg}")
    raise StopValidation(error_msg)


class LoginUsernameValidator:
    def __call__(self, form, field):
        u = users.get_by_name(field.data)
        if not u:
            msg = "User not found"
            error(f"Unable to log in: {msg}")
            raise StopValidation(msg)


class LoginPasswordValidator:
    def __call__(self, form, field):
        u = users.get_by_name(form.username.data)
        if u and not u.login(field.data):
            msg = "Invalid credentials"
            error(f"Unable to log in: {msg}")
            raise StopValidation(msg)


class SignupUsernameValidator:
    def __call__(self, form, field):
        u = users.get_by_name(field.data)
        if u:
            msg = "Username already in use"
            error(f"Unable to sign up: {msg}")
            raise StopValidation(msg)


class SignupPasswordValidator:
    def __call__(self, form, field):
        if field.data != form.password.data:
            msg = "Passwords do not match"
            error(f"Unable to sign up: {msg}")
            raise StopValidation(msg)


class SettingsSecretKeyValidator:
    def __call__(self, form, field):
        if not field.data:
            return
        if len(field.data) != CryptoUtils.KEY_LEN:
            msg = f"Must be a {CryptoUtils.KEY_LEN} characters long string."
            stop_validation(field, msg)


class SettingsPortValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < config.MIN_PORT or field.data > config.MAX_PORT:
            msg = f"Must be an integer value between {config.MIN_PORT} and {config.MAX_PORT}."
            stop_validation(field, msg)


class SettingsLoginAttemptsValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < 0:
            msg = "Must be an integer value equal to or greater than 0."
            stop_validation(field, msg)
