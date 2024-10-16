"""The Bayrol Poolmanager integration."""

from __future__ import annotations

import logging

# from typing import TypedDict
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigValidationError
from homeassistant.helpers import discovery

from .api import PoolPumpAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]
PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]


# TODO Create ConfigEntry type alias with API object
# Create a type alias for ConfigEntryData to store API instances
# class PoolPumpEntryData(TypedDict):
#     api: PoolPumpAPI


# TODO Rename type alias and update all entry annotations
type PoolPumpConfigEntry = ConfigEntry[PoolPumpAPI]  # noqa: F821


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Bayrol Poolmanager from configuration.yaml."""
    if DOMAIN not in config:
        _LOGGER.warning("DOMAIN %s not found in the YAML configuration", DOMAIN)
        return False

    devices_config = config[DOMAIN].get("devices", [])
    if not devices_config:
        _LOGGER.error("No pool pumps found in configuration.yaml")
        return False

    # Store each device (pump) in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["devices"] = []

    for device_config in devices_config:
        name = device_config.get(CONF_NAME)
        host = device_config.get(CONF_HOST)
        username = device_config.get(CONF_USERNAME)
        password = device_config.get(CONF_PASSWORD)
        device_type = device_config.get(
            "type", "pump"
        )  # No built-in constant for 'pump'

        if not host or not username or not password:
            raise ConfigValidationError(f"Missing configuration data for pump {name}")

        _LOGGER.debug("Setting up device with Name: %s, Host: %s", name, host)

        # Create an instance of the PoolPumpAPI asynchronously
        api = await hass.async_add_executor_job(
            lambda: PoolPumpAPI(host, username, password)
        )
        _LOGGER.debug("New API instance created")

        discovery_info = {
            "api": api,
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            "type": device_type,  # No built-in constant for custom types
        }

        # Set up platforms (e.g., sensor) for this pump
        for platform in PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    platform,
                    DOMAIN,
                    discovery_info,
                    config,
                )
            )

    _LOGGER.debug("Platforms set up successfully for all devices")

    return True
