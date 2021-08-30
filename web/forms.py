from random import randint
from typing import List, Tuple

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, PasswordField, SubmitField, RadioField, SelectField, IntegerField, \
    TextAreaField
from wtforms.validators import DataRequired

from core.config.linguard_config import config as linguard_config
from core.config.logger_config import config as logger_config
from core.config.web_config import config as web_config
from core.config_manager import config_manager
from core.crypto_utils import CryptoUtils
from core.models import Interface
from system_utils import get_network_adapters, get_system_interfaces, get_default_gateway, list_to_str
from web.utils import fake
from web.validators import LoginUsernameValidator, LoginPasswordValidator, SignupPasswordValidator, \
    SignupUsernameValidator, SettingsSecretKeyValidator, SettingsPortValidator, SettingsLoginAttemptsValidator, \
    InterfaceIpValidator, InterfaceNameValidator, InterfacePortValidator


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), LoginUsernameValidator()],
                           render_kw={"placeholder": "Enter username"})
    password = PasswordField('Password', validators=[DataRequired(), LoginPasswordValidator()],
                             render_kw={"placeholder": "Enter password"})
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Log in')
    next = StringField()


class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), SignupUsernameValidator()],
                           render_kw={"placeholder": "Enter username"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={"placeholder": "Enter password"})
    confirm = PasswordField('Confirm password', validators=[DataRequired(), SignupPasswordValidator()],
                            render_kw={"placeholder": "Confirm password"})
    submit = SubmitField('Create account')
    next = StringField()


class SettingsForm(FlaskForm):
    ifaces = {}
    for k, v in get_network_adapters().items():
        ifaces[k] = (k, v)
    web_adapter = SelectField("Listen interface", choices=ifaces.values(), default=web_config.host)
    web_port = IntegerField("Listen port", validators=[SettingsPortValidator()],
                            render_kw={"placeholder": f"{web_config.DEFAULT_BINDPORT}", "type": "number"},
                            default=web_config.bindport)
    web_login_attempts = IntegerField("Maximum login attempts", validators=[SettingsLoginAttemptsValidator()],
                                      render_kw={"placeholder": f"{web_config.DEFAULT_LOGIN_ATTEMPTS}",
                                                 "type": "number"},
                                      default=web_config.login_attempts)
    web_secret_key = StringField("Secret key", validators=[SettingsSecretKeyValidator()],
                                 render_kw={"placeholder": f'A {CryptoUtils.KEY_LEN} characters long secret key'},
                                 default=web_config.secret_key)
    web_credentials_file = StringField("Credentials file", render_kw={"placeholder": "path/to/file"},
                                       default=web_config.credentials_file)

    app_config_file = StringField("Configuration file", render_kw={"disabled": "disabled"},
                                  default=config_manager.config_filepath)
    app_endpoint = StringField("Endpoint", render_kw={"placeholder": "vpn.example.com"},
                               default=linguard_config.endpoint)
    app_interfaces_folder = StringField("Interfaces' directory", render_kw={"placeholder": "path/to/folder"},
                                        default=linguard_config.interfaces_folder)
    app_wg_bin = StringField("wg bin", render_kw={"placeholder": "path/to/file", "value": linguard_config.wg_bin})
    app_wg_quick_bin = StringField("wg-quick bin", render_kw={"placeholder": "path/to/file"},
                                   default=linguard_config.wg_quick_bin)
    app_iptables_bin = StringField("iptables bin", render_kw={"placeholder": "path/to/file"},
                                   default=linguard_config.iptables_bin)

    log_overwrite = RadioField("Overwrite", choices=["Yes", "No"], default="Yes" if logger_config.overwrite else "No")
    log_file = StringField("Logfile", render_kw={"placeholder": "path/to/file"}, default=logger_config.logfile)
    log_level = SelectField(choices=logger_config.LEVELS.keys(), default=logger_config.level)

    submit = SubmitField('Save')


class InterfaceForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), InterfaceNameValidator()])
    auto = BooleanField("Auto", default=True)
    description = TextAreaField("Description", render_kw={"placeholder": "Some details..."})
    gateway = SelectField("Gateway", validate_choice=False)
    ipv4 = StringField("IPv4", validators=[DataRequired(), InterfaceIpValidator()],
                       render_kw={"placeholder": "0.0.0.0/32"})
    port = IntegerField("Listen port", validators=[InterfacePortValidator()],
                        render_kw={"placeholder": "25000", "type": "number"})
    on_up = TextAreaField("On up")
    on_down = TextAreaField("On up")
    iface = None
    submit = SubmitField('Add')

    @classmethod
    def get_choices(cls, exclusions: List[str]) -> List[Tuple[str, str]]:
        gateways = list(set(get_system_interfaces().keys()) - set(exclusions))
        choices = []
        for choice in gateways:
            choices.append((choice, choice))
        return choices

    @classmethod
    def from_form(cls, form: "InterfaceForm") -> "InterfaceForm":
        new_form = InterfaceForm()
        new_form.name.data = form.name.data
        new_form.gateway.choices = cls.get_choices(exclusions=["lo"])
        new_form.gateway.data = form.gateway.data
        new_form.ipv4.data = form.ipv4.data
        new_form.port.data = form.port.data
        new_form.on_up.data = form.on_up.data
        new_form.on_down.data = form.on_down.data
        return new_form

    @classmethod
    def populate(cls, form: "InterfaceForm") -> "InterfaceForm":
        name = Interface.generate_valid_name()
        form.name.data = name
        form.gateway.choices = cls.get_choices(exclusions=["lo"])
        gw = get_default_gateway()
        form.gateway.data = gw
        form.ipv4.data = f"{fake.ipv4_private()}/{randint(8, 30)}"
        form.port.data = Interface.get_unused_port()
        form.on_up.data = list_to_str([
            f"{linguard_config.iptables_bin} -I FORWARD -i {name} -j ACCEPT\n" +
            f"{linguard_config.iptables_bin} -I FORWARD -o {name} -j ACCEPT\n" +
            f"{linguard_config.iptables_bin} -t nat -I POSTROUTING -o {gw} -j MASQUERADE\n"
        ])
        form.on_down.data = list_to_str([
            f"{linguard_config.iptables_bin} -D FORWARD -i {name} -j ACCEPT\n" +
            f"{linguard_config.iptables_bin} -D FORWARD -o {name} -j ACCEPT\n" +
            f"{linguard_config.iptables_bin} -t nat -D POSTROUTING -o {gw} -j MASQUERADE\n"
        ])
        return form


class InterfaceEditForm(InterfaceForm):
    public_key = StringField("Public key", render_kw={"disabled": "disabled"})
    private_key = StringField("Private key", render_kw={"disabled": "disabled"})
    submit = SubmitField('Save')

    @classmethod
    def from_form(cls, form: "InterfaceEditForm", iface: Interface) -> "InterfaceEditForm":
        new_form = InterfaceEditForm()
        new_form.iface = iface
        new_form.name.data = form.name.data
        new_form.gateway.choices = cls.get_choices(exclusions=["lo", form.name])
        new_form.gateway.data = form.gateway.data
        new_form.ipv4.data = form.ipv4.data
        new_form.port.data = form.port.data
        new_form.on_up.data = form.on_up.data
        new_form.on_down.data = form.on_down.data
        new_form.public_key.data = iface.public_key
        new_form.private_key.data = iface.private_key
        return new_form

    @classmethod
    def from_interface(cls, iface: Interface) -> "InterfaceEditForm":
        form = InterfaceEditForm()
        form.iface = iface
        form.name.data = iface.name
        form.description.data = iface.description
        form.ipv4.data = iface.ipv4_address
        form.port.data = iface.listen_port
        form.gateway.choices = cls.get_choices(exclusions=["lo", form.name])
        form.gateway.data = iface.gw_iface
        form.on_up.data = list_to_str(iface.on_up, separator="\n")
        form.on_down.data = list_to_str(iface.on_down, separator="\n")
        form.auto.data = iface.auto
        form.public_key.data = iface.public_key
        form.private_key.data = iface.private_key
        return form
