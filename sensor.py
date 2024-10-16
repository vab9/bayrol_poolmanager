"""TemperatureSensor platform."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# from . import HubConfigEntry
from .api import PoolPumpAPI
from .const import DOMAIN, PumpData, PumpMode

_LOGGER = logging.getLogger(__name__)

# ////////


class PoolPumpSensorBase(SensorEntity):
    """Base class for the pool pump sensors."""

    def __init__(self, api: PoolPumpAPI, name: str, unique_id_suffix: str) -> None:
        """Initialize the pool pump sensor."""
        self._api = api
        self._name = name
        self._attr_unique_id = f"{self._api._host}_{unique_id_suffix}"
        self._attr_available = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self._attr_available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._name)},
            name=self._name,
            manufacturer="Bayrol",
            model="Poolmanager",
        )

    async def fetch_data(self, data: PumpData):
        """Fetch the data from the pool pump."""
        try:
            status = await self._api.get_filter_pump_data([data])
            self._attr_available = status is not None
        except Exception as e:
            _LOGGER.error("Failed to update data for %s: %s", self._name, e)
            self._attr_available = False
            return None
        else:
            msg = f"Updating {data.name} to {status.get(data.value)}"
            _LOGGER.debug(msg)
            return status


class TemperatureSensor(PoolPumpSensorBase):
    """Representation of the pool pump temperature sensor."""

    device_class = SensorDeviceClass.TEMPERATURE
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = "measurement"

    def __init__(self, api: PoolPumpAPI, name: str) -> None:
        """Initialize the temperature sensor."""
        super().__init__(api, name, "tempsensor")
        self._temperature = None

    @property
    def state(self) -> float | None:
        """Return the temperature of the pool."""
        return self._temperature if self.available else None

    async def async_update(self) -> None:
        """Fetch the current temperature from the pump."""
        result = await self.fetch_data(PumpData.TEMPERATURE)
        if result:
            self._temperature = result.get(PumpData.TEMPERATURE.value)


class PumpModeSensor(PoolPumpSensorBase):
    """Representation of the pool pump mode sensor."""

    device_class = SensorDeviceClass.ENUM

    def __init__(self, api: PoolPumpAPI, name: str) -> None:
        """Initialize the pump mode sensor."""
        super().__init__(api, name, "pumpmodesensor")
        self._mode: PumpMode = None

    @property
    def state(self) -> PumpMode | None:
        """Return the mode of the pool pump."""
        return self._mode if self.available else None

    @property
    def options(self):
        """Return the list of possible pump modes."""
        return [mode.name for mode in PumpMode]

    async def async_update(self) -> None:
        """Fetch the current mode from the pump."""
        result = await self.fetch_data(PumpData.CURRENT_PUMP_MODE)
        if result:
            mode_number = int(result.get(PumpData.CURRENT_PUMP_MODE.value))
            self._mode = PumpMode(mode_number)


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

    async_add_entities([TemperatureSensor(api, name), PumpModeSensor(api, name)])
