"""TemperatureSensor platform."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_HOST, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import PoolPumpAPI
from .const import DOMAIN, PumpData

_LOGGER = logging.getLogger(__name__)


class TemperatureSensor(SensorEntity):
    """Representation of the pool pump temperature sensor."""

    device_class = SensorDeviceClass.TEMPERATURE
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = "measurement"

    def __init__(self, api: PoolPumpAPI, name: str) -> None:
        """Initialize the temperature sensor."""
        self._name = name
        self._api = api
        self._temperature = None
        self._attr_unique_id = f"{api._host}_{name}_temp"
        self._attr_available = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._name)},
            name=self._name,
            manufacturer="Bayrol",
            model="Poolmanager",
        )

    @property
    def state(self) -> float | None:
        """Return the temperature of the pool."""
        return self._temperature if self.available else None

    async def async_update(self) -> None:
        """Fetch the current temperature from the pump."""
        try:
            result = await self._api.get_filter_pump_data([PumpData.TEMPERATURE])
        except Exception as e:
            self._attr_available = False
        if result:
            self._attr_available = True
            _LOGGER.debug(result)
            self._temperature = result.get(PumpData.TEMPERATURE)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pool pump temperature sensor."""
    if discovery_info is None:
        return

    api = discovery_info.get("api")
    name = discovery_info.get(CONF_NAME)
    host = discovery_info.get(CONF_HOST)

    # Authenticate during setup of select entity
    if not await api.authenticated():
        _LOGGER.debug("During setup, api is still unauthenticated")
        _LOGGER.debug("Logging in")

        if not await api.login():
            raise PlatformNotReady(f"Could not login to pool pump at: {host}")
        _LOGGER.debug("Authenticated successfully for device: %s", name)

    async_add_entities(
        [TemperatureSensor(api, name)],
        update_before_add=True,
    )
