from wtforms.validators import StopValidation

from core.config.web_config import config
from core.crypto_utils import CryptoUtils
from web.models import users


class LoginUsernameValidator:
    def __call__(self, form, field):
        u = users.get_by_name(field.data)
        if not u:
            raise StopValidation("User not found")


class LoginPasswordValidator:
    def __call__(self, form, field):
        u = users.get_by_name(field.data)
        if u and not u.login(field.data):
            raise StopValidation("Invalid credentials")


class SignupUsernameValidator:
    def __call__(self, form, field):
        u = users.get_by_name(field.data)
        if u:
            raise StopValidation("Username already in use")


class SignupPasswordValidator:
    def __call__(self, form, field):
        if field.data != form.password.data:
            raise StopValidation("Passwords do not match")


class SettingsSecretKeyValidator:
    def __call__(self, form, field):
        if not field.data:
            return
        if len(field.data) != CryptoUtils.KEY_LEN:
            raise StopValidation(f"Must be a {CryptoUtils.KEY_LEN} characters long string.")


class SettingsPortValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < config.MIN_PORT or field.data > config.MAX_PORT:
            raise StopValidation(f"Must be an integer value between {config.MIN_PORT} and {config.MAX_PORT}")


class SettingsLoginAttemptsValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < 0:
            raise StopValidation(f"Must be an integer value equal to or greater than 0.")
