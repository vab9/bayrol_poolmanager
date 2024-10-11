"""Pump Controller API to interact with the web interface."""

import logging
import re

import httpx
from .const import PumpData, PumpMode

_LOGGER = logging.getLogger(__name__)


class PoolPumpAPI:
    """Handles communication with the pool pump API, including authentication."""

    def __init__(self, host, username, password):
        """Initialize the API with host, username, and password."""
        self._host = host
        self._base_url = f"http://{self._host}/cgi-bin/webgui.fcgi"
        self._username = username
        self._password = password
        self._session = httpx.AsyncClient()

    async def get_session_id(self):
        """Retrieve a new session id from the login page."""
        # get session id
        _LOGGER.info("Obtaining new session ID")
        try:
            auth_response = await self._session.get(self._base_url)
            _LOGGER.debug("Auth response received")
        except Exception as e:
            _LOGGER.error("Failed to get auth response: %s", e)
            return False

        sid = re.search(r"wui\.init\('([A-Za-z0-9]+)'", auth_response.text).group(1)

        if not sid:
            _LOGGER.error("Failed to retrieve session ID from auth response")
            return False

        self._session.params = self._session.params.set("sid", sid)
        _LOGGER.debug("New session ID: %s", self._session.params["sid"])
        return True

    async def login(self):
        """Authenticate the session with the pool pump."""
        # Make sure we have a session ID
        if "sid" not in self._session.params:
            await self.get_session_id()

        # Check if we are already authenticated
        _LOGGER.debug("Initial auth check in login function")
        if await self.authenticated():
            return True

        url = self._base_url

        # prepare the login payload
        login_payload = {
            "set": {"9.17401.user": self._username, "9.17401.pass": self._password}
        }
        _LOGGER.debug("Login payload: %s", login_payload)

        # Login with username and password
        try:
            login_response = await self._session.post(url, json=login_payload)
            _LOGGER.debug("Login request URL: %s", login_response.request.url)
            _LOGGER.debug("Login response json: %s", login_response.json())

        except Exception as e:
            _LOGGER.error("Failed to send login request: %s", e)
            return False
        else:
            # TODO: Should use the authenticated method!?
            expected_result = login_response.json()["event"]["data"] == "3.16912.0"
            if expected_result and await self.authenticated():
                _LOGGER.debug("Successfully authenticated with the pool pump")
                return True

    async def authenticated(self):
        """Return True if the session is authenticated."""
        # to check if we are authenticated / logged in, we try to access the menu
        try:
            menu_response = await self._session.get(
                self._base_url, params={"cmd": "2.17005.0"}
            )

        except Exception as e:
            _LOGGER.error("Failed to send menu get request: %s", e)
            return False

        title = extract_title(menu_response)
        _LOGGER.debug("Response HTML title: %s", title)

        if title == "icon":
            _LOGGER.debug("The session is authenticated")
            return True
        if title == "PM5":
            _LOGGER.debug("The session is not authenticated")
            return False
        _LOGGER.error("Unexpected response to menu request. Not authenticated")
        return False

    async def elevate_service_level(self, level):
        """Elevate the service level for setting operations."""
        service_level_map = {
            1: 1234,
            2: 5678,
        }

        if level not in service_level_map:
            raise ValueError(
                f"Invalid service level: {level}. Valid modes are: 1 and 2 only."
            )

        if not await self.authenticated():
            if not await self.login():
                _LOGGER.error("Failed to authenticate before elevating service level")
                return False

        # preflight request to get service code:
        try:
            cmd = {"cmd": "1.1360.0"}

            # session params are merged in httpx !?
            res = await self._session.get(self._base_url, params=cmd)
            _LOGGER.debug(res.request.url)
            _LOGGER.debug(res.url)
            # _LOGGER.debug(res.text)
            title = extract_title(res)
            if title == "access":
                key = re.search(r"42\.802\d\.code", res.text).group(0)
            elif title == "menu":
                _LOGGER.debug("Service level is already elevated")
                return True
            else:
                _LOGGER.warning("Unexpected title in preflight response: %s", title)
                return False
        except (AttributeError, Exception) as e:
            _LOGGER.error("Error fetching service code: %s", e)
            return False

        # set payload
        payload = {"set": {key: str(service_level_map[level])}}
        _LOGGER.debug("service level payload: %s", payload)

        # try to elevate service level
        try:
            response = await self._session.post(self._base_url, json=payload)

            # post service level elevation validation request !?
            response2 = await self._session.get(
                self._base_url, params={"cmd": "3.16912.0"}
            )

            return (
                response.json().get("event", {}).get("data") == "1.1360.0"
                and response2.status_code == 200
            )
        except Exception as e:
            _LOGGER.error("Failed to elevate service level: %s", e)
            return False

    async def set_filter_pump_mode(self, mode: str):
        """Set the pump mode."""
        try:
            mode_enum = PumpMode[mode.upper()]  # Convert string to PumpMode
        except KeyError:
            _LOGGER.error("Invalid mode: %s", mode)
            return False

        _LOGGER.debug("BEFORE: %s", self._session.params.get("sid"))

        # (re-)authorize session if necessary
        if not await self.authenticated():
            if not await self.login():
                _LOGGER.warning("Could not set filter pump mode")
                return False

        _LOGGER.debug("AFTER: %s", self._session.params.get("sid"))

        # Elevate service level to 2
        if not await self.elevate_service_level(2):
            _LOGGER.error("Failed to elevate service level")
            return False
        try:
            pump_payload = {
                "get": ["60.5427.value", "1.1256.value", "1.1246.value"],
                "set": {"60.5427.value": mode_enum.value},
            }
            _LOGGER.debug(pump_payload)
            response = await self._session.post(self._base_url, json=pump_payload)
            _LOGGER.debug(response.request.url)
            _LOGGER.debug(response.request.headers)
            # _LOGGER.debug(response.request.content)
            _LOGGER.debug(response.json())

        except Exception as e:
            _LOGGER.error("Error setting pump mode: %s", e)
            return False
        else:
            return response.json()["status"]["code"] == 0

    async def get_filter_pump_data(self, data):
        """Retrieve various data from the filter pump."""
        if not isinstance(data, list):
            raise TypeError("data must be a list of PumpData")
        if not all(isinstance(d, PumpData) for d in data):
            raise TypeError("data must contain instances of PumpData")

        data_values = [d.value for d in data]
        _LOGGER.debug("Data values: %s", data_values)

        try:
            response = await self._session.post(
                self._base_url,
                json={"get": data_values},
            )
            result = response.json()["data"]
            _LOGGER.debug("Received response data for the filter pump: %s", result)

        except Exception as e:
            _LOGGER.warning("Error getting pump data: %s", e)
            return None
        else:
            return result

    async def available(self):
        """Return True if the filter pump is reachable, False otherwise."""
        try:
            res = await self._session.get(self._base_url)
        except Exception as e:
            _LOGGER.warning("Cannot reach pump")
            _LOGGER.warning(e)
            return False
        else:
            _LOGGER.debug(res.status_code)
            return res.status_code == 200


def extract_title(response):
    """Return the HTML title of a response."""
    res = re.search(r"<title>(.*?)</title>", response.text, re.DOTALL)
    return res.group(1).strip()
