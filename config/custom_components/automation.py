"""
Custom Automation Component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import logging

from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_ON, STATE_OFF
import homeassistant.loader as loader
from homeassistant.helpers import validate_config
import homeassistant.components as core

# The domain of your component. Should be equal to the name of your component
DOMAIN = "automation"

# List of component names (string) your component depends upon
# We depend on group because group will be loaded after all the components that
# initalize devices have been setup.
DEPENDENCIES = ['group', 'nest']

# Configuration key for "nest away" control.
CONF_NEST_AWAY_CTRL = 'nest_away_control'

# Entity Id for "nest away" control.
NEST_STATE_AWAY_ID = 'nest.state_away'

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Setup automation. """

    # Validate that all required config options are given
    if not validate_config(config, {DOMAIN: [CONF_NEST_AWAY_CTRL]}, _LOGGER):
        return False

    nest_away_ctrl = int(config[DOMAIN][CONF_NEST_AWAY_CTRL])

    if nest_away_ctrl == 1:
        # Validate that the target entity id exists
        if hass.states.get(NEST_STATE_AWAY_ID) is None:
            _LOGGER.error("Entity id %s does not exist", NEST_STATE_AWAY_ID)

            # Tell the bootstrapper that we failed to initialize
            return False

    # We will use the component helper methods to check the states.
    device_tracker = loader.get_component('device_tracker')

    def control_nest_away (entity_id, old_state, new_state):
        """ Called when the group.all devices change state. """

        # If anyone comes home and "nest away" is on, turn it off.
        if new_state.state == STATE_HOME and core.is_on(hass, NEST_STATE_AWAY_ID):
            core.turn_off(hass, NEST_STATE_AWAY_ID)

        # If all people leave the house and "nest away" is off, turn it on
        elif new_state.state == STATE_NOT_HOME and not core.is_on(hass, NEST_STATE_AWAY_ID):
            core.turn_on(hass, NEST_STATE_AWAY_ID)

    if nest_away_ctrl == 1:
        # Register control_nest_away method to receive state changes of the
        # all tracked devices group.
        hass.states.track_change(device_tracker.ENTITY_ID_ALL_DEVICES, control_nest_away)

    return True