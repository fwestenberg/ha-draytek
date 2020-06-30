"""This component provides basic support for TP-Link WiFi router."""
import logging
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, ATTR_ENTITY_ID, STATE_ON, STATE_OFF, STATE_UNKNOWN, STATE_UNAVAILABLE
from custom_components.draytek_wifi.PyPi.draytek import routerDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "DrayTek Router"
DOMAIN = "draytek_router"
DEFAULT_USERNAME = "user"

STATE_ICONS = {
    STATE_ON: "mdi:wifi",
    STATE_OFF: "mdi:wifi-off",
    STATE_UNKNOWN: "mdi:wifi-strength-0",
    STATE_UNAVAILABLE: "mdi:wifi-strength-warning-outline"
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a DrayTek WiFi Router."""
    add_entities([DrayTekRouter(hass, config)], update_before_add=True)

class DrayTekRouter(SwitchDevice):
    """An implementation of a TP-Link WiFi Router."""

    def __init__(self, hass, config):
        super().__init__()

        self._host = config.get(CONF_HOST)
        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._name = config.get(CONF_NAME)
        self._state = STATE_UNAVAILABLE
        self._hass = hass
        self._manager = routerDevice(self._host, self._username, self._password)

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == STATE_ON:
            return True
        else:
            return False

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return STATE_ICONS.get(self._state, None)

    @property
    def available(self):
        """Return true if switch is available."""
        if self._state == STATE_UNAVAILABLE:
            return False
        else:
            return True

    def turn_on(self, **kwargs):
        """Turn the WiFi on."""
        self._state = STATE_ON
        self._icon = STATE_ICONS.get(self._state, None)
        self._hass.states.set(self.entity_id, self._state)
        self._hass.loop.create_task(self._manager.set_wifi_state(STATE_ON))

    def turn_off(self, **kwargs):
        """Turn the WiFi off."""
        self._state = STATE_OFF
        self._icon = STATE_ICONS.get(self._state, None)
        self._hass.states.set(self.entity_id, self._state)
        self._hass.loop.create_task(self._manager.set_wifi_state(STATE_OFF))

    def update(self):
        """Update the state"""
        self._state = self._manager.get_wifi_state()