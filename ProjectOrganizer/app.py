import os

from flask import Flask, jsonify
from flask_cors import CORS

from controllers.authentification_controller import auth_bp
from repository.database import db
from utils.errors import register_error_handlers


def creer_app() -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["JWT_SECRET"] = os.environ["JWT_SECRET"]

    CORS(app)
    db.init_app(app)
    register_error_handlers(app)

    app.register_blueprint(auth_bp)

    @app.get("/health")
    def health():
        return jsonify({"statut": "ok"}), 200

    return app


app = creer_app()

if __name__ == "__main__":
    app.run(debug=True)
