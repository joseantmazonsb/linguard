import traceback
from logging import fatal, error, debug


def log_exception(e: Exception, is_fatal: bool = False):
    error_msg = str(e) or f"{e.__class__.__name__} exception thrown by {e.__class__.__module__}"
    if is_fatal:
        fatal(error_msg)
    else:
        error(error_msg)
    debug(f"{traceback.format_exc()}")
