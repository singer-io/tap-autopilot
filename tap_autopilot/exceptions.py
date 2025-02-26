class AutopilotError(Exception):
    """class representing Generic Http error."""

    def __init__(self, message=None, response=None):
        super().__init__(message)
        self.message = message
        self.response = response


class AutopilotBackoffError(AutopilotError):
    """class representing backoff error handling."""

    pass


class AutopilotBadRequestError(AutopilotError):
    """class representing 400 status code."""

    pass


class AutopilotUnauthorizedError(AutopilotError):
    """class representing 401 status code."""

    pass


class AutopilotForbiddenError(AutopilotError):
    """class representing 403 status code."""

    pass


class AutopilotNotFoundError(AutopilotError):
    """class representing 404 status code."""

    pass


class AutopilotConflictError(AutopilotError):
    """class representing 406 status code."""

    pass


class AutopilotUnprocessableEntityError(AutopilotBackoffError):
    """class representing 409 status code."""

    pass


class AutopilotRateLimitError(AutopilotBackoffError):
    """class representing 429 status code."""

    pass


class AutopilotInternalServerError(AutopilotBackoffError):
    """class representing 500 status code."""

    pass


class AutopilotNotImplementedError(AutopilotBackoffError):
    """class representing 501 status code."""

    pass


class AutopilotBadGatewayError(AutopilotBackoffError):
    """class representing 502 status code."""

    pass


class AutopilotServiceUnavailableError(AutopilotBackoffError):
    """class representing 503 status code."""

    pass


ERROR_CODE_EXCEPTION_MAPPING = {
    400: {
        "raise_exception": AutopilotBadRequestError,
        "message": "A validation exception has occurred.",
    },
    401: {
        "raise_exception": AutopilotUnauthorizedError,
        "message": "The access token provided is expired, revoked, malformed or invalid for other reasons.",
    },
    403: {
        "raise_exception": AutopilotForbiddenError,
        "message": "You are missing the following required scopes: read",
    },
    404: {
        "raise_exception": AutopilotNotFoundError,
        "message": "The resource you have specified cannot be found.",
    },
    409: {
        "raise_exception": AutopilotConflictError,
        "message": "The API request cannot be completed because the requested operation would conflict with an existing item.",
    },
    422: {
        "raise_exception": AutopilotUnprocessableEntityError,
        "message": "The request content itself is not processable by the server.",
    },
    429: {
        "raise_exception": AutopilotRateLimitError,
        "message": "The API rate limit for your organisation/application pairing has been exceeded.",
    },
    500: {
        "raise_exception": AutopilotInternalServerError,
        "message": "The server encountered an unexpected condition which prevented"
        " it from fulfilling the request.",
    },
    501: {
        "raise_exception": AutopilotNotImplementedError,
        "message": "The server does not support the functionality required to fulfill the request.",
    },
    502: {
        "raise_exception": AutopilotBadGatewayError,
        "message": "Server received an invalid response.",
    },
    503: {
        "raise_exception": AutopilotServiceUnavailableError,
        "message": "API service is currently unavailable.",
    },
}
