from typing import Any, Dict, Mapping, Optional, Tuple

import backoff
import requests
from requests import session
from requests.exceptions import Timeout, ConnectionError, ChunkedEncodingError
from singer import get_logger, metrics

from tap_autopilot.exceptions import (
    ERROR_CODE_EXCEPTION_MAPPING,
    AutopilotError,
    AutopilotBackoffError,
)

LOGGER = get_logger()
REQUEST_TIMEOUT = 300


def raise_for_error(response: requests.Response) -> None:
    """Raises the associated response exception. Takes in a response object,
    checks the status code, and throws the associated exception based on the
    status code.

    :param resp: requests.Response object
    """
    try:
        response_json = response.json()
    except Exception:
        response_json = {}
    if response.status_code != 200:
        if response_json.get("error"):
            message = f"HTTP-error-code: {response.status_code}, Error: {response_json.get('error')}"
        else:
            error_message = ERROR_CODE_EXCEPTION_MAPPING.get(
                response.status_code, {}
            ).get("message", "Unknown Error")
            message = f"HTTP-error-code: {response.status_code}, Error: {response_json.get('message', error_message)}"

        exc = ERROR_CODE_EXCEPTION_MAPPING.get(response.status_code, {}).get(
            "raise_exception", AutopilotError
        )
        raise exc(message, response) from None


class Client:
    """A Wrapper class. ~~~

    Performs:
     - Authentication
     - Response parsing
     - HTTP Error handling and retry
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = config
        self._session = session()
        # self.base_url = "https://api2.autopilothq.com/v1"
        self.base_url = "https://private-ef2f41-autopilot.apiary-mock.com/v1"

        config_request_timeout = config.get("request_timeout")
        self.request_timeout = (
            float(config_request_timeout) if config_request_timeout else REQUEST_TIMEOUT
        )

    def __enter__(self):
        self.check_api_credentials()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

    def check_api_credentials(self) -> None:
        pass

    def authenticate(self, headers: Dict, params: Dict) -> Tuple[Dict, Dict]:
        """Authenticates the request with the token."""
        headers["autopilotapikey"] = self.config["api_key"]
        if "user_agent" in self.config:
            headers["user-agent"] = self.config["user_agent"]

        return headers, params

    def get(self, endpoint: str, params: Dict, headers: Dict, path: str = None) -> Any:
        """Calls the make_request method with a prefixed method type `GET`"""
        headers, params = self.authenticate(headers, params)
        LOGGER.info(f"Fetching data from {endpoint}")
        return self.__make_request(
            "GET",
            endpoint,
            headers=headers,
            params=params,
            timeout=self.request_timeout,
        )

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(
            ConnectionResetError,
            ConnectionError,
            ChunkedEncodingError,
            Timeout,
            AutopilotBackoffError,
        ),
        max_tries=5,
        factor=2,
    )
    def __make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Mapping[Any, Any]]:
        """Performs HTTP Operations."""
        with metrics.http_request_timer(endpoint):
            response = self._session.request(method, endpoint, **kwargs)
            raise_for_error(response)

        return response.json()
