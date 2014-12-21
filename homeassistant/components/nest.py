import logging
from homeassistant.helpers import validate_config
from homeassistant.const import (ATTR_ENTITY_PICTURE, ATTR_CUSTOM_GROUP_STATE, ATTR_UNIT_OF_MEASUREMENT)
from datetime import datetime

# The domain of your component. Should be equal to the name of your component
DOMAIN = "nest"
ENTITY_TEMP_INSIDE_ID = "nest.temperature_inside"
ENTITY_TEMP_TARGET_ID = "nest.temperature_target"


# Configuration key for the entity id we are targetting
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []

def setup(hass, config):
    """ Setup NEST thermostat. """

    # Validate that all required config options are given
    if not validate_config(config, {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]}, _LOGGER):
        return False

    try:
        import homeassistant.external.pynest.nest as pynest
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pynest. "))
        return False

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    mynest = pynest.Nest(username, password, None)
    mynest.login()

    def nest_temp(time):
        """ Method to get the current inside and target temperatures. """

        mynest.get_status()
        current_temperature = mynest.get_curtemp()
        target_temperature = mynest.get_tartemp()


        hass.states.set(ENTITY_TEMP_INSIDE_ID, current_temperature, {ATTR_UNIT_OF_MEASUREMENT: mynest.get_units(), ATTR_CUSTOM_GROUP_STATE: "nest",ATTR_ENTITY_PICTURE:
                     "https://cdn2.iconfinder.com/data/icons/windows-8-metro-ui-weather-report/512/Temperature.png"})

        hass.states.set(ENTITY_TEMP_TARGET_ID, target_temperature, {ATTR_UNIT_OF_MEASUREMENT: mynest.get_units(), ATTR_CUSTOM_GROUP_STATE: "nest",ATTR_ENTITY_PICTURE:
                     "http://d1hwvnnkb0v1bo.cloudfront.net/content/art/app/icons/target_icon.jpg"})

    hass.track_time_change(nest_temp, minute=[0,30], second=0)

    nest_temp(datetime.now())

    # Tells the bootstrapper that the component was succesfully initialized
    return True




