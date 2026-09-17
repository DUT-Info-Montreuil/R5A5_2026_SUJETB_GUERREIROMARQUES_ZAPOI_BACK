
from flask import Flask, jsonify


class ApiError(Exception):
    code = 500
    erreur = "Internal Server Error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(ApiError):
    code = 400
    erreur = "Bad Request"


class Unauthorized(ApiError):
    code = 401
    erreur = "Unauthorized"


class Forbidden(ApiError):
    code = 403
    erreur = "Forbidden"


class NotFound(ApiError):
    code = 404
    erreur = "Not Found"


class Conflict(ApiError):
    code = 409
    erreur = "Conflict"


class UnprocessableEntity(ApiError):
    code = 422
    erreur = "Unprocessable Entity"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return jsonify({"erreur": err.erreur, "detail": err.detail}), err.code

    @app.errorhandler(404)
    def handle_404(_err):
        return jsonify({"erreur": "Not Found", "detail": "Route inconnue."}), 404

    @app.errorhandler(500)
    def handle_500(_err):
        return jsonify({"erreur": "Internal Server Error", "detail": "Erreur interne."}), 500
