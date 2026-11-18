from typing import Any

from seleniumbase.core import browser_launcher

_set_firefox_options = browser_launcher._set_firefox_options


def _with_bidi(*args: Any, **kwargs: Any) -> Any:
    options = _set_firefox_options(*args, **kwargs)
    options.web_socket_url = True
    return options


# SeleniumBase starts Firefox without BiDi, which slow_requests needs for
# preload scripts, and its --cap-string is read only for remote grids.
browser_launcher._set_firefox_options = _with_bidi
