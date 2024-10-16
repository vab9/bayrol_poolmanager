"""TemperatureSensor platform"""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# from . import HubConfigEntry
from .api import PoolPumpAPI
from .const import DOMAIN, PumpData

_LOGGER = logging.getLogger(__name__)


class TemperatureSensor(SensorEntity):
    """Representation of the pool pump temperature sensor."""

    device_class = SensorDeviceClass.TEMPERATURE
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, api: PoolPumpAPI, name) -> None:
        """Initialize the pool pump temperature sensor."""
        self._api = api
        self._name = name
        self._temperature = None
        # TODO check how to do this properly
        self._attr_unique_id = f"{self._api._host}_tempsensor"
        self._available = False

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
    def available(self) -> bool:
        """Return true if the temperature sensor is available."""
        return self._available

    @property
    def state(self) -> float:
        """Return the temperature of the pool."""
        return self._temperature

    async def async_update(self) -> None:
        """Fetch the current temperature from the pump."""
        try:
            status = await self._api.get_filter_pump_data([PumpData.TEMPERATURE])
            self._available = status is not None
            if status:
                self._temperature = status.get(PumpData.TEMPERATURE.value)
                _LOGGER.debug("Updated status to %s", status)
        except Exception as e:
            _LOGGER.error("Failed to update temperature for %s: %s", self._name, e)


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

    async_add_entities([TemperatureSensor(api, name)])
