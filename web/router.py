from flask import Blueprint

from web.controllers.dashboard import Dashboard
from web.controllers.login import Login
from web.controllers.signup import Signup
from web.controllers.error import NotFound, Unauthorized, InternalServerError

router = Blueprint("router", __name__)


@router.route("/")
def index():
    return Dashboard().load()


@router.route("/login")
def login():
    return Login().load()


@router.route("/signup")
def signup():
    return Signup().load()


@router.app_errorhandler(404)
def not_found(err):
    return NotFound().load(), 404


@router.app_errorhandler(401)
def not_found(err):
    return Unauthorized().load(), 401


@router.app_errorhandler(500)
def not_found(err):
    return InternalServerError().load(), 500
