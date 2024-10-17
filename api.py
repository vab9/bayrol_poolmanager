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
        self._current_data = {}

    async def get_session_id(self):
        """Retrieve a new session id from the login page."""
        # get session id
        _LOGGER.info("Obtaining new session ID")
        try:
            auth_response = await self._session.get(self._base_url)
            _LOGGER.debug("Auth response received")
            sid = re.search(r"wui\.init\('([A-Za-z0-9]+)'", auth_response.text).group(1)
        # TODO several exceptions possible here
        except Exception as e:
            _LOGGER.error("Failed to get auth response: %s", e)
            return False

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
        # TODO remove custom title recognition or use other detection mechanism
        if "Can Fig" in title:
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

    async def set_filter_pump_mode(self, mode: PumpMode):
        """Set the pump mode."""
        # (re-)authorize session if necessary
        if not await self.authenticated():
            if not await self.login():
                _LOGGER.warning("Could not login to set filter pump mode")
                return False

        # Elevate service level to 2
        if not await self.elevate_service_level(2):
            _LOGGER.error("Failed to elevate service level")
            return False
        try:
            pump_payload = {
                "get": ["60.5427.value", "1.1256.value", "1.1246.value"],
                "set": {"60.5427.value": mode.value},
            }
            _LOGGER.debug(pump_payload)
            response = await self._session.post(self._base_url, json=pump_payload)
            json_data = response.json()
            # _LOGGER.debug(response.request.url)
            # _LOGGER.debug(response.request.headers)
            # _LOGGER.debug(response.request.content)
            _LOGGER.debug(json_data)

        except Exception as e:
            _LOGGER.error("Error setting pump mode: %s", e)
            return False
        else:
            _LOGGER.debug("json response from setting mode: ")
            _LOGGER.debug(json_data)
            _LOGGER.debug(self._current_data)

            self._current_data[PumpData.PUMP_MODE.value] = json_data.get("data").get(
                PumpData.PUMP_MODE.value
            )
            _LOGGER.warning(self._current_data)
            return json_data.get("data").get(PumpData.PUMP_MODE.value) == mode.value

    async def get_filter_pump_data(self, data):
        """Retrieve various data from the filter pump."""
        _LOGGER.warning(data)
        _LOGGER.warning("-------------")

        if not isinstance(data, list):
            raise TypeError("data must be a list")

        if not all(d.name in PumpData.__members__ for d in data):
            raise TypeError("data must contain valid PumpData enum members")

        # TODO Why does this not work?
        # if not all(d in PumpData for d in data):
        #     # if not all(isinstance(d, Enum) for d in data):
        #     raise TypeError("data must contain PumpData enum")

        json_payload = {"get": [d.value for d in data]}
        _LOGGER.debug("JSON Payload: %s", json_payload)

        try:
            response = await self._session.post(
                self._base_url,
                json=json_payload,
            )
            # Update current data
            self._current_data.update(response.json().get("data"))

        except Exception as e:
            _LOGGER.warning("Error getting pump data: %s", e)
            raise
        else:
            _LOGGER.debug("Get filter pump function is returning data: ")
            _LOGGER.debug({key: self._current_data[key.value] for key in data})
            return {key: self._current_data[key.value] for key in data}

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
