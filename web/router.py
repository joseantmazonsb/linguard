from flask import Blueprint
from web.controller import Controller

router = Blueprint("router", __name__)


@router.route("/")
@router.route("/dashboard")
def index():
    context = {
        "title": "Dashboard"
    }
    return Controller("web/index.html", **context).load()


@router.route("/login")
def login():
    context = {
        "title": "Login"
    }
    return Controller("web/login.html", **context).load()


@router.route("/signup")
def signup():
    context = {
        "title": "Sign up"
    }
    return Controller("web/signup.html", **context).load()


@router.app_errorhandler(401)
def not_found(err):
    error_code = 401
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": "Unauthorized"
    }
    return Controller("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(404)
def not_found(err):
    error_code = 404
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": "Resource not found :(",
        "image": "/static/assets/img/error-404-monochrome.svg"
    }
    return Controller("error/error-img.html", **context).load(), error_code


@router.app_errorhandler(500)
def not_found(err):
    error_code = 500
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": "Internal server error"
    }
    return Controller("error/error-main.html", **context).load(), error_code
