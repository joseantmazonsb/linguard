import ipaddress
from logging import error

from flask_login import current_user
from wtforms.validators import StopValidation

from core.config.web_config import config
from core.crypto_utils import CryptoUtils
from core.models import Interface, Peer
from web.models import users


def stop_validation(field, error_msg):
    error(f"Unable to validate field '{field.label.text}': {error_msg}")
    raise StopValidation(error_msg)


class LoginUsernameValidator:
    def __call__(self, form, field):
        u = users.get_value_by_attr("name", field.data)
        if not u:
            msg = "User not found"
            error(f"Unable to log in: {msg}")
            raise StopValidation(msg)


class LoginPasswordValidator:
    def __call__(self, form, field):
        u = users.get_value_by_attr("name", form.username.data)
        if u and not u.login(field.data):
            msg = "Invalid credentials"
            error(f"Unable to log in: {msg}")
            raise StopValidation(msg)


class SignupUsernameValidator:
    def __call__(self, form, field):
        u = users.get_value_by_attr("name", field.data)
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
            msg = f"must be a {CryptoUtils.KEY_LEN} characters long string."
            stop_validation(field, msg)


class SettingsLoginAttemptsValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < 0:
            msg = "must be an integer value equal to or greater than 0."
            stop_validation(field, msg)


class InterfaceNameValidator:
    def __call__(self, form, field):
        if not Interface.is_name_valid(field.data):
            msg = f"can only contain alphanumeric characters, underscores (_) and " \
                  f"hyphens (-). It must also begin with a letter and be between {Interface.MIN_NAME_LENGTH} and " \
                  f"{Interface.MAX_NAME_LENGTH} characters long."
            stop_validation(field, msg)
        if Interface.is_name_in_use(field.data, form.iface):
            stop_validation(field, "already in use!")


class InterfaceIpValidator:
    def __call__(self, form, field):
        try:
            ipaddress.IPv4Interface(field.data)
            if Interface.is_ip_in_use(field.data, form.iface):
                stop_validation(field, "address already in use!")
        except ValueError:
            msg = "must be valid IPv4 interface. Follow the format 'X.X.X.X/Y'."
            stop_validation(field, msg)


class InterfacePortValidator:
    def __call__(self, form, field):
        if type(field.data) is not int:
            return
        if field.data and field.data < config.MIN_PORT or field.data > config.MAX_PORT:
            msg = f"must be an integer value between {config.MIN_PORT} and {config.MAX_PORT}."
            stop_validation(field, msg)
        if Interface.is_port_in_use(field.data, form.iface):
            stop_validation(field, "port already in use!")


class PeerNameValidator:
    def __call__(self, form, field):
        if not Peer.is_name_valid(field.data):
            msg = f"can only contain alphanumeric characters, underscores (_), " \
                  f"hyphens (-) and whitespaces. It must also begin with a letter and be between {Peer.MIN_NAME_LENGTH} and " \
                  f"{Peer.MAX_NAME_LENGTH} characters long."
            stop_validation(field, msg)


class PeerIpValidator:
    def __call__(self, form, field):
        try:
            ipaddress.IPv4Interface(field.data)
            if Peer.is_ip_in_use(field.data, form.peer):
                stop_validation(field, "address already in use!")
        except ValueError:
            msg = "must be valid IPv4 interface. Follow the format 'X.X.X.X/Y'."
            stop_validation(field, msg)


class PeerPrimaryDnsValidator:
    def __call__(self, form, field):
        try:
            ipaddress.IPv4Address(field.data)
        except ValueError:
            msg = "must be valid IPv4 address. Follow the format 'X.X.X.X'."
            stop_validation(field, msg)


class PeerSecondaryDnsValidator:
    def __call__(self, form, field):
        if not field.data:
            return
        try:
            ipaddress.IPv4Address(field.data)
        except ValueError:
            msg = "must be valid IPv4 address. Follow the format 'X.X.X.X'."
            stop_validation(field, msg)


class NewPasswordValidator:
    def __call__(self, form, field):
        if field.data != form.confirm.data:
            msg = "passwords do not match"
            raise StopValidation(msg)
        if current_user.check_password(field.data):
            raise StopValidation("the new password cannot be the same as the old one!")


class OldPasswordValidator:
    def __call__(self, form, field):
        if not current_user.check_password(field.data):
            msg = "wrong password"
            raise StopValidation(msg)

