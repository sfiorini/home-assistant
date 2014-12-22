import logging
import homeassistant.util as util
from homeassistant.helpers import validate_config, ToggleDevice
from homeassistant.const import (ATTR_ENTITY_PICTURE, ATTR_CUSTOM_GROUP_STATE, ATTR_UNIT_OF_MEASUREMENT, ATTR_FRIENDLY_NAME)
from datetime import datetime, timedelta

# The domain of your component. Should be equal to the name of your component
DOMAIN = "nest"
ENTITY_AWAY_NAME = "state away"
ENTITY_TEMP_INSIDE_ID = "nest.temperature_inside"
ENTITY_TEMP_TARGET_ID = "nest.temperature_target"

ENTITY_AWAY_ID_FORMAT = DOMAIN + '.{}'

# Configuration key for the entity id we are targeting
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

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

    thermostat = NestThermostat(pynest.Nest(username, password, None))
    thermostat.entity_id = ENTITY_AWAY_ID_FORMAT.format(util.slugify(ENTITY_AWAY_NAME))
    print(thermostat.entity_id)
    thermostat.nest.login()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_nest_state(now):
        """ Update nest state. """

        logging.getLogger(__name__).info("Update nest state")

        thermostat.nest.get_status()
        thermostat.update_ha_state(hass)

    update_nest_state(None)

    def nest_temp(time):
        """ Method to get the current inside and target temperatures. """

        #thermostat.nest.get_status()
        current_temperature = thermostat.nest.get_curtemp()
        target_temperature = thermostat.nest.get_tartemp()


        hass.states.set(ENTITY_TEMP_INSIDE_ID, current_temperature, {ATTR_UNIT_OF_MEASUREMENT: thermostat.nest.get_units(), ATTR_CUSTOM_GROUP_STATE: "nest",ATTR_ENTITY_PICTURE:
                     "https://cdn2.iconfinder.com/data/icons/windows-8-metro-ui-weather-report/512/Temperature.png"})

        hass.states.set(ENTITY_TEMP_TARGET_ID, target_temperature, {ATTR_UNIT_OF_MEASUREMENT: thermostat.nest.get_units(), ATTR_CUSTOM_GROUP_STATE: "nest",ATTR_ENTITY_PICTURE:
                     "http://d1hwvnnkb0v1bo.cloudfront.net/content/art/app/icons/target_icon.jpg"})

    hass.track_time_change(nest_temp, minute=[0,30], second=0)

    nest_temp(datetime.now())

    # Tells the bootstrapper that the component was succesfully initialized
    return True

class NestThermostat(ToggleDevice):


    def __init__(self, nest):
        self.nest = nest
        self.state_attr = {ATTR_FRIENDLY_NAME: ENTITY_AWAY_NAME}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return ENTITY_AWAY_NAME

    def turn_on(self, **kwargs):
        """ Turns away on. """
        self.nest.set_away("away")

    def turn_off(self):
        """ Turns away off. """
        self.nest.set_away("here")

    def is_on(self):
        """ True if away is on. """
        return self.nest.is_away()

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

