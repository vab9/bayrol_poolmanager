"""Constants for the Bayrol Poolmanager integration."""

from enum import Enum

DOMAIN = "bayrol_poolmanager"


class PumpMode(Enum):
    ECO = 1
    NORMAL = 2
    HIGH = 4
    AUTO = 8
    OFF = 16


class PumpData(Enum):
    TEMPERATURE = "34.4033.value"
    PH_VALUE = "34.4001.value"
    CURRENT_PUMP_MODE = "60.5427.value"
