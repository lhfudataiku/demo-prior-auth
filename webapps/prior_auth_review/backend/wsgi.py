from pathlib import Path
from webaiku.extension import WEBAIKU
from webapps.prior_auth_review.backend.backend import api

WEBAPP_DIST = "webapps/prior_auth_review/dist"


def init_dss_app(app):
    WEBAIKU(app, WEBAPP_DIST)
    WEBAIKU.extend(app, [api])


if "app" in globals():
    init_dss_app(app)  # type: ignore[name-defined]


if __name__ == "__main__":
    raise SystemExit(
        "wsgi.py is the DSS entrypoint and expects the DSS runtime. "
        "For local development, run webapps/prior_auth_review/backend/wsgi_local.py instead."
    )
