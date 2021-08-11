from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, PasswordField, SubmitField, RadioField, SelectField, IntegerField
from wtforms.validators import DataRequired

from core.app_manager import manager
from core.config.linguard_config import config as linguard_config
from core.config.logger_config import config as logger_config
from core.config.web_config import config as web_config
from core.crypto_utils import CryptoUtils
from web.validators import LoginUsernameValidator, LoginPasswordValidator, SignupPasswordValidator, \
    SignupUsernameValidator, SettingsSecretKeyValidator, SettingsPortValidator, SettingsLoginAttemptsValidator


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

    web_port = IntegerField("Port", validators=[SettingsPortValidator()],
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
                                  default=manager.config_filepath)
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
