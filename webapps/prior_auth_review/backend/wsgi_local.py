import os
from pathlib import Path
import sys

from flask import Flask

try:
    from webaiku.extension import WEBAIKU
except ModuleNotFoundError:  # pragma: no cover
    WEBAIKU = None


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
WEBAPP_ROOT = BACKEND_DIR.parent
WEBAPP_DIST = str(WEBAPP_ROOT / "dist")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webapps.prior_auth_review.backend.backend import api


def create_local_app():
    flask_app = Flask(__name__)
    api_port = int(os.getenv("VITE_API_PORT", "5001"))
    if WEBAIKU is not None and Path(WEBAPP_DIST).exists():
        WEBAIKU(flask_app, WEBAPP_DIST, api_port)
        WEBAIKU.extend(flask_app, [api])
        return flask_app

    flask_app.register_blueprint(api)
    return flask_app


app = create_local_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("VITE_API_PORT", "5001")), debug=True)
