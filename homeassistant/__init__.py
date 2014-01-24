"""
homeassistant
~~~~~~~~~~~~~

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""

import time
import logging
import threading
from collections import namedtuple
import datetime as dt

import homeassistant.util as util

logging.basicConfig(level=logging.INFO)

MATCH_ALL = '*'

DOMAIN = "homeassistant"

STATE_ON = "on"
STATE_OFF = "off"
STATE_NOT_HOME = 'device_not_home'
STATE_HOME = 'device_home'

SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"
SERVICE_HOMEASSISTANT_STOP = "stop"

EVENT_HOMEASSISTANT_START = "homeassistant.start"
EVENT_STATE_CHANGED = "state_changed"
EVENT_TIME_CHANGED = "time_changed"

TIMER_INTERVAL = 10  # seconds

# We want to be able to fire every time a minute starts (seconds=0).
# We want this so other modules can use that to make sure they fire
# every minute.
assert 60 % TIMER_INTERVAL == 0, "60 % TIMER_INTERVAL should be 0!"


def start_home_assistant(bus):
    """ Start home assistant. """
    request_shutdown = threading.Event()

    bus.register_service(DOMAIN, SERVICE_HOMEASSISTANT_STOP,
                         lambda service: request_shutdown.set())

    Timer(bus)

    bus.fire_event(EVENT_HOMEASSISTANT_START)

    while not request_shutdown.isSet():
        try:
            time.sleep(1)

        except KeyboardInterrupt:
            break


def _process_match_param(parameter):
    """ Wraps parameter in a list if it is not one and returns it. """
    if not parameter:
        return MATCH_ALL
    elif isinstance(parameter, list):
        return parameter
    else:
        return [parameter]


def _matcher(subject, pattern):
    """ Returns True if subject matches the pattern.

    Pattern is either a list of allowed subjects or a `MATCH_ALL`.
    """
    return MATCH_ALL == pattern or subject in pattern


def split_entity_id(entity_id):
    """ Splits a state entity_id into domain, object_id. """
    return entity_id.split(".", 1)


def filter_entity_ids(entity_ids, domain_filter=None, strip_domain=False):
    """ Filter a list of entities based on domain. Setting strip_domain
        will only return the object_ids. """
    return [
        split_entity_id(entity_id)[1] if strip_domain else entity_id
        for entity_id in entity_ids if
        not domain_filter or entity_id.startswith(domain_filter)
        ]


def track_state_change(bus, entity_id, action, from_state=None, to_state=None):
    """ Helper method to track specific state changes. """
    from_state = _process_match_param(from_state)
    to_state = _process_match_param(to_state)

    def listener(event):
        """ State change listener that listens for specific state changes. """
        if entity_id == event.data['entity_id'] and \
                _matcher(event.data['old_state'].state, from_state) and \
                _matcher(event.data['new_state'].state, to_state):

            action(event.data['entity_id'],
                   event.data['old_state'],
                   event.data['new_state'])

    bus.listen_event(EVENT_STATE_CHANGED, listener)


# pylint: disable=too-many-arguments
def track_time_change(bus, action,
                      year=None, month=None, day=None,
                      hour=None, minute=None, second=None,
                      point_in_time=None, listen_once=False):
    """ Adds a listener that will listen for a specified or matching time. """
    pmp = _process_match_param
    year, month, day = pmp(year), pmp(month), pmp(day)
    hour, minute, second = pmp(hour), pmp(minute), pmp(second)

    def listener(event):
        """ Listens for matching time_changed events. """
        now = event.data['now']

        mat = _matcher

        if (point_in_time and now > point_in_time) or \
           (not point_in_time and
                mat(now.year, year) and
                mat(now.month, month) and
                mat(now.day, day) and
                mat(now.hour, hour) and
                mat(now.minute, minute) and
                mat(now.second, second)):

            # point_in_time are exact points in time
            # so we always remove it after fire
            if listen_once or point_in_time:
                event.bus.remove_event_listener(EVENT_TIME_CHANGED, listener)

            action(now)

    bus.listen_event(EVENT_TIME_CHANGED, listener)

ServiceCall = namedtuple("ServiceCall", ["bus", "domain", "service", "data"])
Event = namedtuple("Event", ["bus", "event_type", "data"])


class Bus(object):
    """ Class that allows different components to communicate via services
    and events.
    """

    def __init__(self):
        self._event_listeners = {}
        self._services = {}
        self.logger = logging.getLogger(__name__)
        self.event_lock = threading.Lock()
        self.service_lock = threading.Lock()

    @property
    def services(self):
        """ Dict with per domain a list of available services. """
        with self.service_lock:
            return {domain: self._services[domain].keys()
                    for domain in self._services}

    @property
    def event_listeners(self):
        """ Dict with events that is being listened for and the number
        of listeners.
        """
        with self.event_lock:
            return {key: len(self._event_listeners[key])
                    for key in self._event_listeners}

    def call_service(self, domain, service, service_data=None):
        """ Calls a service. """
        with self.service_lock:
            try:
                self._services[domain][service]
            except KeyError:
                # Domain or Service does not exist
                raise ServiceDoesNotExistException(
                    "Service does not exist: {}/{}".format(domain, service))

            service_data = service_data or {}

            def run():
                """ Executes a service. """
                service_call = ServiceCall(self, domain, service, service_data)

                try:
                    self._services[domain][service](service_call)
                except Exception:  # pylint: disable=broad-except
                    self.logger.exception(
                        "Bus:Exception in service {}/{}".format(
                            domain, service))

            # We dont want the bus to be blocking - run in a thread.
            threading.Thread(target=run).start()

    def register_service(self, domain, service, service_callback):
        """ Register a service. """
        with self.service_lock:
            try:
                self._services[domain][service] = service_callback
            except KeyError:
                # Domain does not exist yet
                self._services[domain] = {service: service_callback}

    def fire_event(self, event_type, event_data=None):
        """ Fire an event. """
        with self.event_lock:
            # Copy the list of the current listeners because some listeners
            # choose to remove themselves as a listener while being executed
            # which causes the iterator to be confused.
            get = self._event_listeners.get
            listeners = get(MATCH_ALL, []) + get(event_type, [])

            self.logger.info("Bus:Event {}: {}".format(
                             event_type, event_data))

            if not listeners:
                return

            event_data = event_data or {}

            def run():
                """ Fire listeners for event. """
                event = Event(self, event_type, event_data)

                for listener in listeners:
                    try:
                        listener(event)
                    except Exception:  # pylint: disable=broad-except
                        self.logger.exception(
                            "Bus:Exception in event listener")

            # We dont want the bus to be blocking - run in a thread.
            threading.Thread(target=run).start()

    def listen_event(self, event_type, listener):
        """ Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        with self.event_lock:
            try:
                self._event_listeners[event_type].append(listener)
            except KeyError:  # event_type did not exist
                self._event_listeners[event_type] = [listener]

    def listen_once_event(self, event_type, listener):
        """ Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Note: at the moment it is impossible to remove a one time listener.
        """
        def onetime_listener(event):
            """ Removes listener from eventbus and then fires listener. """
            self.remove_event_listener(event_type, onetime_listener)

            listener(event)

        self.listen_event(event_type, onetime_listener)

    def remove_event_listener(self, event_type, listener):
        """ Removes a listener of a specific event_type. """
        with self.event_lock:
            try:
                self._event_listeners[event_type].remove(listener)

                # delete event_type list if empty
                if not self._event_listeners[event_type]:
                    del self._event_listeners[event_type]

            except (KeyError, ValueError):
                # KeyError is key event_type did not exist
                # ValueError if the list [event_type] did not contain listener
                pass


class State(object):
    """ Object to represent a state within the state machine. """

    __slots__ = ['entity_id', 'state', 'attributes', 'last_changed']

    def __init__(self, entity_id, state, attributes=None, last_changed=None):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        last_changed = last_changed or dt.datetime.now()

        # Strip microsecond from last_changed else we cannot guarantee
        # state == State.from_dict(state.as_dict())
        # This behavior occurs because to_dict uses datetime_to_str
        # which strips microseconds
        if last_changed.microsecond:
            self.last_changed = last_changed - dt.timedelta(
                microseconds=last_changed.microsecond)
        else:
            self.last_changed = last_changed

    def copy(self):
        """ Creates a copy of itself. """
        return State(self.entity_id, self.state,
                     dict(self.attributes), self.last_changed)

    def as_dict(self):
        """ Converts State to a dict to be used within JSON.
        Ensures: state == State.from_dict(state.as_dict()) """

        return {'entity_id': self.entity_id,
                'state': self.state,
                'attributes': self.attributes,
                'last_changed': util.datetime_to_str(self.last_changed)}

    @staticmethod
    def from_dict(json_dict):
        """ Static method to create a state from a dict.
        Ensures: state == State.from_json_dict(state.to_json_dict()) """

        try:
            last_changed = json_dict.get('last_changed')

            if last_changed:
                last_changed = util.str_to_datetime(last_changed)

            return State(json_dict['entity_id'],
                         json_dict['state'],
                         json_dict.get('attributes'),
                         last_changed)
        except KeyError:  # if key 'state' did not exist
            return None

    def __repr__(self):
        return "<state {}:{}, {}>".format(
            self.state, self.attributes,
            util.datetime_to_str(self.last_changed))


class StateMachine(object):
    """ Helper class that tracks the state of different entities. """

    def __init__(self, bus):
        self.states = {}
        self.bus = bus
        self.lock = threading.Lock()

    @property
    def entity_ids(self):
        """ List of entitie ids that are being tracked. """
        with self.lock:
            return self.states.keys()

    def remove_entity(self, entity_id):
        """ Removes a entity from the state machine.

        Returns boolean to indicate if a entity was removed. """
        with self.lock:
            try:
                del self.states[entity_id]

                return True

            except KeyError:
                # if entity does not exist
                return False

    def set_state(self, entity_id, new_state, attributes=None):
        """ Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state. """

        attributes = attributes or {}

        with self.lock:
            # Change state and fire listeners
            try:
                old_state = self.states[entity_id]

            except KeyError:
                # If state did not exist yet
                self.states[entity_id] = State(entity_id, new_state,
                                               attributes)

            else:
                if old_state.state != new_state or \
                   old_state.attributes != attributes:

                    state = self.states[entity_id] = \
                        State(entity_id, new_state, attributes)

                    self.bus.fire_event(EVENT_STATE_CHANGED,
                                        {'entity_id': entity_id,
                                         'old_state': old_state,
                                         'new_state': state})

    def get_state(self, entity_id):
        """ Returns the state of the specified entity. """
        with self.lock:
            try:
                # Make a copy so people won't mutate the state
                return self.states[entity_id].copy()

            except KeyError:
                # If entity does not exist
                return None

    def is_state(self, entity_id, state):
        """ Returns True if entity exists and is specified state. """
        try:
            return self.get_state(entity_id).state == state
        except AttributeError:
            # get_state returned None
            return False


class Timer(threading.Thread):
    """ Timer will sent out an event every TIMER_INTERVAL seconds. """

    def __init__(self, bus):
        threading.Thread.__init__(self)

        self.daemon = True
        self.bus = bus

        bus.listen_once_event(EVENT_HOMEASSISTANT_START,
                              lambda event: self.start())

    def run(self):
        """ Start the timer. """

        logging.getLogger(__name__).info("Timer:starting")

        last_fired_on_second = -1

        calc_now = dt.datetime.now

        while True:
            now = calc_now()

            # First check checks if we are not on a second matching the
            # timer interval. Second check checks if we did not already fire
            # this interval.
            if now.second % TIMER_INTERVAL or \
               now.second == last_fired_on_second:

                # Sleep till it is the next time that we have to fire an event.
                # Aim for halfway through the second that fits TIMER_INTERVAL.
                # If TIMER_INTERVAL is 10 fire at .5, 10.5, 20.5, etc seconds.
                # This will yield the best results because time.sleep() is not
                # 100% accurate because of non-realtime OS's
                slp_seconds = TIMER_INTERVAL - now.second % TIMER_INTERVAL + \
                    .5 - now.microsecond/1000000.0

                time.sleep(slp_seconds)

                now = calc_now()

            last_fired_on_second = now.second

            self.bus.fire_event(EVENT_TIME_CHANGED,
                                {'now': now})


class HomeAssistantError(Exception):
    """ General Home Assistant exception occured. """


class ServiceDoesNotExistError(HomeAssistantError):
    """ A service has been referenced that deos not exist. """
