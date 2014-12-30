""" Support for WeMo switchces. """
import logging

from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_HOSTS


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return WeMo switches. """

    try:
        # Pylint does not play nice if not every folders has an __init__.py
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pywemo.pywemo as pywemo
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return []

    if CONF_HOSTS in config:
        switches = (pywemo.device_from_host(host) for host
                    in config[CONF_HOSTS].split(","))

    else:
        logging.getLogger(__name__).info("Scanning for WeMo devices")
        switches = pywemo.discover_devices()

    # Filter out the switches and wrap in WemoSwitch object
    return [WemoSwitch(switch) for switch in switches
            if isinstance(switch, pywemo.Switch)]


class WemoSwitch(ToggleDevice):
    """ represents a WeMo switch within home assistant. """
    def __init__(self, wemo):
        self.wemo = wemo
        self.state_attr = {ATTR_FRIENDLY_NAME: wemo.name}

    def get_name(self):
        """ Returns the name of the switch if any. """
        result = ""
        try:
            result = self.wemo.name
        except Exception as e:
            logging.getLogger(__name__).error( "Wemo Get Name failed: %s", e.message)

        return result

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        try:
            self.wemo.on()
        except Exception as e:
            logging.getLogger(__name__).error( "Wemo On failed: %s", e.message)

    def turn_off(self):
        """ Turns the switch off. """
        try:
            self.wemo.off()
        except Exception as e:
            logging.getLogger(__name__).error( "Wemo Off failed: %s", e.message)

    def is_on(self):
        """ True if switch is on. """
        result = False
        try:
            result = self.wemo.get_state(True)
        except Exception as e:
            logging.getLogger(__name__).error( "Wemo Is On failed: %s", e.message)

        return result

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr
