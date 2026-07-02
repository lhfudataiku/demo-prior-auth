from pathlib import Path

from flask import send_from_directory

from webapps.prior_auth_review.backend.backend import api, compat

WEBAPP_DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


def _register_spa(app):
    """Serve the built Vite SPA directly from Flask.

    We deliberately do NOT use webaiku's ServeBlueprint here: it rewrites
    index.html with an injected `<base href>` derived from a `?URL=` query
    param the DSS iframe never sends, which produces `<base href="None/">` and
    404s every bundled asset (blank page). Instead we serve index.html verbatim
    and expose /assets/<file> so the bundle's relative `./assets/...` references
    resolve against the iframe URL. Mirrors the bs-blueprint FastAPI approach.
    """

    @app.route("/")
    def _spa_index():
        return send_from_directory(WEBAPP_DIST_DIR, "index.html")

    @app.route("/assets/<path:filename>")
    def _spa_assets(filename: str):
        return send_from_directory(WEBAPP_DIST_DIR / "assets", filename)


def init_dss_app(app):
    app.register_blueprint(api)
    app.register_blueprint(compat)
    _register_spa(app)


if "app" in globals():
    init_dss_app(app)  # type: ignore[name-defined]


if __name__ == "__main__":
    raise SystemExit(
        "wsgi.py is the DSS entrypoint and expects the DSS runtime. "
        "For local development, run webapps/prior_auth_review/backend/wsgi_local.py instead."
    )
