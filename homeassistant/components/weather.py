import logging
import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (ATTR_ENTITY_PICTURE)
from datetime import datetime, timedelta

# The domain of your component. Should be equal to the name of your component
DOMAIN = "weather"
ENTITY_WEATHER_CURRENT_ID = "weather.current_weather"

# Configuration key for the entity id we are targeting
CONF_ZIPCODE = 'zip'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []

def setup(hass, config):
    """ Setup Weather. """

    # Validate that all required config options are given
    if not validate_config(config, {DOMAIN: [CONF_ZIPCODE]}, _LOGGER):
        return False

    try:
        import homeassistant.external.pyweather.weather as weather
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pyweather. "))
        return False

    zip_code = config[DOMAIN][CONF_ZIPCODE]

    # Create the command line parser.
    cli_parser = weather.create_cli_parser()

    # Get the options and arguments.
    args = cli_parser.parse_args(['-d', ' ', zip_code])

    # Initialize report.
    myweather = MyWeather()

    # Limit the requested forecast days.
    if args.forecast > weather.DAYS_LIMIT or args.forecast < 0:
        cli_parser.error("Days to forecast must be between 0 and %d"
                         % weather.DAYS_LIMIT)


    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_weather(now):
        """ Get weather update. """

        logging.getLogger(__name__).info("Update weather.")

         # Get the weather.
        weather_update = weather.get_weather(zip_code, args)

        # Create the report.
        myweather.report = weather.create_report(weather_update, args)

    # Update state every 15 minutes
    hass.track_time_change(update_weather, minute=[0,15,30,45])
    update_weather(None)

    def current_weather(time):
        """ Method to get the current outside temperature and weather conditions. """
        hass.states.set(ENTITY_WEATHER_CURRENT_ID, myweather.report, {ATTR_ENTITY_PICTURE: "http://mediad.publicbroadcasting.net/p/wunc/files/201403/weather-153703_640.png"})

    hass.track_time_change(current_weather, minute=[1,16,31,46])

    current_weather(datetime.now())

    return True

class MyWeather(object):

    def __init__(self):
        self.strReport = "No Data Available"

    @property
    def report(self):
        return self.strReport

    @report.setter
    def report(self, value):
        self.strReport = value