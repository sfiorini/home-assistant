"""
homeassistant.components.device_sun_light_trigger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to turn on lights based on
the state of the sun and devices.
"""
import logging
from datetime import datetime, timedelta

import homeassistant as ha

from . import light, sun, device_tracker, general, group


LIGHT_TRANSITION_TIME = timedelta(minutes=15)


# pylint: disable=too-many-branches
def setup(bus, statemachine, light_group=None):
    """ Triggers to turn lights on or off based on device precense. """

    logger = logging.getLogger(__name__)

    device_state_categories = ha.filter_categories(statemachine.categories,
                                                   device_tracker.DOMAIN)

    if not device_state_categories:
        logger.error("LightTrigger:No devices found to track")

        return False

    if not light_group:
        light_group = light.STATE_GROUP_NAME_ALL_LIGHTS

    # Get the light IDs from the specified group
    light_ids = ha.filter_categories(
        group.get_categories(statemachine, light_group), light.DOMAIN, True)

    if not light_ids:
        logger.error("LightTrigger:No lights found to turn on ")

        return False

    # Calculates the time when to start fading lights in when sun sets
    time_for_light_before_sun_set = lambda: \
        (sun.next_setting(statemachine) - LIGHT_TRANSITION_TIME *
         len(light_ids))

    # pylint: disable=unused-argument
    def handle_sun_rising(category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        def turn_light_on_before_sunset(light_id):
            """ Helper function to turn on lights slowly if there
                are devices home and the light is not on yet. """
            if (device_tracker.is_home(statemachine) and
               not light.is_on(statemachine, light_id)):

                light.turn_on(bus, light_id, LIGHT_TRANSITION_TIME.seconds)

        def turn_on(light_id):
            """ Lambda can keep track of function parameters but not local
            parameters. If we put the lambda directly in the below statement
            only the last light will be turned on.. """
            return lambda now: turn_light_on_before_sunset(light_id)

        start_point = time_for_light_before_sun_set()

        for index, light_id in enumerate(light_ids):
            ha.track_time_change(bus, turn_on(light_id),
                                 point_in_time=(start_point +
                                                index * LIGHT_TRANSITION_TIME))

    # Track every time sun rises so we can schedule a time-based
    # pre-sun set event
    ha.track_state_change(bus, sun.STATE_CATEGORY, handle_sun_rising,
                          sun.STATE_BELOW_HORIZON, sun.STATE_ABOVE_HORIZON)

    # If the sun is already above horizon
    # schedule the time-based pre-sun set event
    if sun.is_up(statemachine):
        handle_sun_rising(None, None, None)

    def handle_device_state_change(category, old_state, new_state):
        """ Function to handle tracked device state changes. """
        lights_are_on = group.is_on(statemachine, light_group)

        light_needed = not (lights_are_on or sun.is_up(statemachine))

        # Specific device came home ?
        if (category != device_tracker.STATE_CATEGORY_ALL_DEVICES and
           new_state['state'] == ha.STATE_HOME):

            # These variables are needed for the elif check
            now = datetime.now()
            start_point = time_for_light_before_sun_set()

            # Do we need lights?
            if light_needed:

                logger.info(
                    "Home coming event for {}. Turning lights on".
                    format(category))

                for light_id in light_ids:
                    light.turn_on(bus, light_id)

            # Are we in the time span were we would turn on the lights
            # if someone would be home?
            # Check this by seeing if current time is later then the point
            # in time when we would start putting the lights on.
            elif start_point < now < sun.next_setting(statemachine):

                # Check for every light if it would be on if someone was home
                # when the fading in started and turn it on if so
                for index, light_id in enumerate(light_ids):

                    if now > start_point + index * LIGHT_TRANSITION_TIME:
                        light.turn_on(bus, light_id)

                    else:
                        # If this light didn't happen to be turned on yet so
                        # will all the following then, break.
                        break

        # Did all devices leave the house?
        elif (category == device_tracker.STATE_CATEGORY_ALL_DEVICES and
              new_state['state'] == ha.STATE_NOT_HOME and lights_are_on):

            logger.info(
                "Everyone has left but there are devices on. Turning them off")

            general.shutdown_devices(bus, statemachine)

    # Track home coming of each seperate device
    for category in device_state_categories:
        ha.track_state_change(bus, category, handle_device_state_change,
                              ha.STATE_NOT_HOME, ha.STATE_HOME)

    # Track when all devices are gone to shut down lights
    ha.track_state_change(bus, device_tracker.STATE_CATEGORY_ALL_DEVICES,
                          handle_device_state_change, ha.STATE_HOME,
                          ha.STATE_NOT_HOME)

    return True
