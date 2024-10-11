"""Select platform for Bayrol Poolmanager integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import PoolPumpAPI
from .const import DOMAIN, PumpData, PumpMode

_LOGGER = logging.getLogger(__name__)


class PoolPumpModeSelect(SelectEntity):
    """Representation of a select entity to control the pool pump's mode."""

    def __init__(self, api: PoolPumpAPI, name: str) -> None:
        """Initialize the pool pump mode select."""
        self._api = api
        self._name = name
        self._attr_options = [
            mode.name for mode in PumpMode
        ]  # List of available pump modes
        self._attr_current_option = None
        self._attr_unique_id = f"{self._api._host}_mode_select"
        self._available = False

    @property
    def name(self) -> str:
        """Return the name of the select entity."""
        return f"{self._name} Mode"

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
        """Return True if the pump is reachable."""
        return self._available

    async def async_select_option(self, option: str) -> None:
        """Set the pump to the selected mode."""
        _LOGGER.debug("Setting pump mode for %s to %s", self._name, option)
        try:
            # Find the corresponding PumpMode from the option string
            success = await self._api.set_filter_pump_mode(option)
            if success:
                self._attr_current_option = option
                _LOGGER.info("Pump mode for %s set to %s", self._name, option)
            else:
                _LOGGER.error(
                    "Failed to set pump mode for %s to %s", self._name, option
                )
        except KeyError:
            _LOGGER.error("Invalid pump mode selected: %s", option)
            raise
        except Exception as e:
            _LOGGER.error("Error setting pump mode for %s: %s", self._name, e)

    async def async_update(self) -> None:
        """Fetch the current mode of the pool pump to update the select entity."""
        _LOGGER.debug("Updating the pump mode for %s", self._name)
        try:
            status = await self._api.get_filter_pump_data([PumpData.CURRENT_PUMP_MODE])
            self._available = status is not None
            if status:
                current_mode_value = int(status.get(PumpData.CURRENT_PUMP_MODE.value))
                self._attr_current_option = PumpMode(current_mode_value).name
                _LOGGER.debug(
                    "Current pump mode for %s: %s",
                    self._name,
                    self._attr_current_option,
                )
        except Exception as e:
            _LOGGER.error("Failed to update pump mode for %s: %s", self._name, e)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pool pump mode select entity."""
    if discovery_info is None:
        return

    devices = hass.data[DOMAIN].get("devices", [])
    selects = []

    for device in devices:
        api = device["api"]
        name = device["name"]

        if device["type"] == "pump":
            selects.append(PoolPumpModeSelect(api, name))

    async_add_entities(selects, True)
