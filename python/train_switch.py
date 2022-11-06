"""Train switch classes"""
import time
from abc import abstractmethod
from typing import Tuple, Optional
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero.pins.mock import MockFactory
from gpiozero import DigitalOutputDevice
from gpiozero import AngularServo
from threading import Timer


PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter - half seconds
BLINK = 0.25  # default time to wait between blinking
SAFE_SHUTDOWN = 4.0  # how long to wait before shutting down disconnect
PIN_FACTORY = PiGPIOFactory()
# PIN_FACTORY = MockFactory()

class BinaryDevice:
    required_pins = None # Number of pins required (i.e. 2).
    on_state = None # Since only two states, this is the "on" state.
    off_state = None # ... and the "off" state.

    def __init__(
        self,
        pin: Tuple[int],
        logger: object = None) -> None:
        """ Abstract base class for any device with two states.

        Args:
            pin: Unique number for a gpio pin on a raspberry pi.
                Alternatively a tuple of integers for multi-pin devices.
            verbose: Either True or False. Verbosity of object.
            logger: logging object passed from Flask server.
        """
        self.__name__ = 'Base Train Switch'
        pin = tuple(sorted(pin))  # always sort the pins
        self.__pin = pin
        self.__state = None
        self.logger = logger

    @property
    def name(self) -> str:
        """Returns the name of the object."""
        return self.__name__

    @property
    def pin(self) -> str:
        """Returns the pin number(s)."""
        return self.__pin

    @property
    def pin_list(self) -> list:
        """Returns a list of used pin(s)"""
        return list(self.__pin)

    @property
    def pin_string(self) -> str:
        """Returns a csv seperated string of pin(s)"""
        return ','.join(str(s) for s in self.__pin)

    @property
    def get_required_pins(self) -> int:
        return self.required_pins

    @property
    def state(self) -> str:
        """Returns the active state."""
        return self.__state

    @state.setter
    def state(self, state: str) -> None:
        self.custom_state_setter(state)
        self.__state = state

    @abstractmethod
    def custom_state_setter(self, state: Optional[str]) -> None:
        """Custom action upon setting the state."""
        pass

    def __repr__(self):
        return f"{self.name} @ Pin : {self.pin}"

    def to_json(self) -> dict:
        """Converts an object to a seralized representation.

        Returns:
            Serialized reprsentation including:
                - pin
                - state
                - name
        """
        return {
            'pins': self.pin,
            'state': self.state,
            'name': self.name
        }

    def log(self, initial_state: str, action: str, update: object) -> None:
        """Logs update message"""
        if self.logger:
            self.logger.info(
                f"{self}: \n" +
                f"++++ initial state: {initial_state} \n" +
                f"++++ action: {action} \n" +
                f"++++ update: {update}"
            )

    @staticmethod
    def action_to_angle(action: str) -> int:
        """Maps an action to a legal action."""
        mapping = {
        'turn': 100.0,
        'straight': 180.0
        }
        angle = mapping.get(action, None)

        if isinstance(angle, type(None)):
            raise ValueError(
                "Invalid command to train switch." + 
                f"\n Found action: {action}"
            )
        return angle

    @abstractmethod
    def _action(self, action: str) -> object:
        pass

    def action(self, action: str) -> None:
        """ Execute an action on a train switch.

        If an ordered action is the same as the previous state, then do nothing.
        Otherwise, convert the action to an angle and perform an update to the
        state of the train switch.

        Args:
            action: One of [`straight`, `on`] or [`turn`, `off`]
        """
        if self.state == action:
            self.log(self.state, action, 'skipped')
            return

        # complete derived class's work
        try:
            update = self._action(action)
            self.log(self.state, action, update)

            # remember new state to check against future actions
            self.state = action

        except Exception as ex:
            self.logger.exception(
                f"{self}: \n" +
                f"++++ exception raised: {ex}"
            )

    @abstractmethod
    def __del__(self) -> None:
        pass

    def close(self) -> None:
        """Close a connection with a switch."""
        self.__del__()

        if self.logger:
            self.logger.info(f"++++ {self} is closed...")


class ServoTrainSwitch(BinaryDevice):
    required_pins = 1
    on_state = 'straight'
    off_state = 'turn'

    def __init__(
        self,
        min_angle: float = 100.0,
        max_angle: float = 180.0,
        initial_angle: float = None,
        **kwargs) -> None:
        """ Servo class wrapping the gpiozero class for manual train switches.

        Args:
            min_angle: minimum angle of the angular servo
            max_angle: maximum angle of the angular servo
            initial_angle: intial angle of the servo

        References:
            https://gpiozero.readthedocs.io/en/stable/api_output.html#angularservo
            https://gpiozero.readthedocs.io/en/stable/recipes.html#servo

        Notes:
            The default pin factory for this device is:
            `gpio.zero.pins.pigpio.PiGPIOFactory`
            and cannot be mixed with other pin factories:
            https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
        """
        super(ServoTrainSwitch, self).__init__(**kwargs)

        # gpiozero API expects "BOARD" in front of the pin #
        self.__name__ = 'Servo Train Switch'
        if len(self.pin) != self.get_required_pins:
            raise ValueError(f"Expecting two pins. Found {self.pin}")
        self.pin_name = "BOARD" + str(self.pin[0])
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.initial_angle = initial_angle

        # Supporting math:
        # params for SG90 micro servo:
        # 50Hz normal operation
        # 2% duty cycle = 0°
        # 12% duty cycle = 12°
        # => frame_width (s) = 1 / 50 (Hz) = 0.02 (s)
        # _min_dc = min_pulse_width / frame_width = 0.02%
        # => min_pulse = 4 / 10,000
        # _dc_range = (max_pulse_width - min_pulse_width) / frame_width = 0.12%
        # => max_pulse_width = 24 / 10,000
        self.servo = AngularServo(
            min_angle=self.min_angle,
            max_angle=self.max_angle,
            initial_angle=self.initial_angle,
            pin=self.pin_name,
            frame_width=1/PULSE,  # 1/50Hz corresponds to 20/1000s default
            min_pulse_width=4/10000,  # corresponds to 2% duty cycle
            max_pulse_width=24/10000,  # correponds to 12% duty cycle
            pin_factory=PIN_FACTORY
        )

        if self.logger:
            self.logger.info(f"++++ {self} is started...")

    def custom_state_setter(self, state: Optional[str]) -> None:
        pass

    def _action(self, action: str) -> object:
        angle = self.action_to_angle(action)
        self.servo.angle = angle
        return angle

    def __del__(self) -> None:
        self.servo.close()

class RelayTrainSwitch(BinaryDevice):
    required_pins = 2
    on_state = 'straight'
    off_state = 'turn'

    def __init__(self, active_high: bool = False, initial_value: bool = False, **kwargs) -> None:
        """ Relay switch wrapping the gpiozero class for remote train switches.

        References:
            https://www.electronicshub.org/control-a-relay-using-raspberry-pi/

        Notes:
            The default pin factory for this device is:
            `gpio.zero.pins.pigpio.PiGPIOFactory`
            and cannot be mixed with other pin factories:
            https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
        """
        super(RelayTrainSwitch, self).__init__(**kwargs)
        self.__name__ = 'Relay Train Switch'

        if not isinstance(self.pin, tuple):
            raise ValueError(f"Expecting multiple pins. Found {self.pin}")

        if len(self.pin) != self.get_required_pins:
            raise ValueError(f"Expecting two pins. Found {self.pin}")

        # when active_high=False, on() seems to pass voltage and off() seems to pass no voltage.
        # We initially set to False.
        self.yg_relay = DigitalOutputDevice(
            pin="BOARD" + str(self.pin[0]),
            active_high=active_high,
            initial_value=initial_value,
            pin_factory=PIN_FACTORY
        )
        self.br_relay = DigitalOutputDevice(
            pin="BOARD" + str(self.pin[1]),
            active_high=active_high,
            initial_value=initial_value,
            pin_factory=PIN_FACTORY
        )

        if self.logger:
            self.logger.info(f"++++ {self} is started...")

    def custom_state_setter(self, state: Optional[str]) -> None:
        if not state:
            self.br_relay.off()
            self.yg_relay.off()

    @staticmethod
    def action_to_conf(action: str):
        """ Map an action to a relay configuration"""
        mapping = {
            'turn': 'br',
            'straight': 'yg',
        }

        conf = mapping.get(action, None)

        if isinstance(conf, type(None)):
            raise ValueError(
                "Invalid command to train switch." +
                f"\n Found action: {action}"
            )

        return conf

    def _action(self, action: str) -> object:
        # we only want to blink one pair at a time
        # otherwise, leave both relays as low - sending no action
        conf = self.action_to_conf(action)

        # Now we `BLINK` a single device once for 1/2 second.
        if conf == 'br':
            self.br_relay.off()
            self.br_relay.on()
            time.sleep(BLINK)
            self.br_relay.off()

        if conf == 'yg':
            self.yg_relay.off()
            self.yg_relay.on()
            time.sleep(BLINK)
            self.yg_relay.off()
        return conf

    def __del__(self) -> None:
        self.yg_relay.close()
        self.br_relay.close()


class OnOff(BinaryDevice):
    required_pins = 1
    on_state = 'on'
    off_state = 'off'

    def __init__(self, active_high: bool = False, initial_value: bool = False, **kwargs) -> None:
        """ OnOff wrapping the gpiozero class for generic devices.

        References:
            https://www.electronicshub.org/control-a-relay-using-raspberry-pi/

        Notes:
            The default pin factory for this device is:
            `gpio.zero.pins.pigpio.PiGPIOFactory`
            and cannot be mixed with other pin factories:
            https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
        """
        super(OnOff, self).__init__(**kwargs)
        self.__name__ = 'On/Off'

        if not isinstance(self.pin, tuple):
            raise ValueError(f"Expecting one pin. Found {self.pin}")

        if len(self.pin) != self.get_required_pins:
            raise ValueError(f"Expecting one pin. Found {self.pin}")

        # when active_high=False, on() seems to pass voltage and off() seems to pass no voltage.
        # We initially set to False.
        self.relay = DigitalOutputDevice(
            pin="BOARD" + str(self.pin[0]),
            active_high=active_high,
            initial_value=initial_value,
            pin_factory=PIN_FACTORY
        )

        if self.logger:
            self.logger.info(f"++++ {self} is started...")

    def custom_state_setter(self, state: Optional[str]) -> None:
        if not state:
            self.relay.off()

    @staticmethod
    def action_to_conf(action: str):
        """ Map an action to a relay configuration"""
        mapping = {
            'off': 'open',
            'on': 'close',
        }

        conf = mapping.get(action, None)

        if isinstance(conf, type(None)):
            raise ValueError(
                "Invalid command to on/off device." +
                f"\n Found action: {action}"
            )

        return conf

    def _action(self, action: str) -> object:
        conf = self.action_to_conf(action)

        if conf == 'open':
            self.relay.off()

        if conf == 'close':
            self.relay.on()
        return conf

    def __del__(self) -> None:
        self.relay.close()


class Disconnect(OnOff):
    """Extension of On/Off for Disconnect accessory."""
    def __init__(self, active_high=False, **kwargs) -> None:
        super(Disconnect, self).__init__(active_high=active_high, **kwargs)
        self.__name__ = "Disconnect"
        self.safe_stop = None

    def safe_close_relay(self) -> None:
        # If relay is on, turn it off
        self.logger.info(
                f"\n {self}: \n" +
                f"++++ Background Thread: Checking for shutdown..."
            )
        if self.relay.value == 1:
            self.logger.info(
                f"\n {self}: \n" +
                f"++++ Background Thread: auto-shutdown"
            )
            self.relay.off()
            self.state = self.off_state
        else:
            self.logger.info(f"\n {self}: \n ++++ Background Thread: no action needed!")

    def _action(self, action: str) -> object:
        conf = self.action_to_conf(action)

        if conf == 'open':
            self.relay.off()
            # If we had a thread waiting to close, cancel it.
            if self.safe_stop is not None:
                self.safe_stop.cancel()
                
        if conf == 'close':
            self.relay.on()
            # Wait for 10 seconds, then turn off.
            self.safe_stop = Timer(SAFE_SHUTDOWN, self.safe_close_relay)
            self.safe_stop.start()

        return conf

    def __del__(self) -> None:
        self.relay.off()
        super().__del__()

        
class Unloader(OnOff):
    """Extension of On/Off for Unloader accessory."""
    def __init__(self, **kwargs) -> None:
        super(Unloader, self).__init__(active_high=False, **kwargs)
        self.__name__ = "Unloader"
        
        
class InvertedDisconnect(Disconnect):
    """Extension of On/Off for Disconnect accessory w/ inverted active_high."""
    def __init__(self, **kwargs) -> None:
        super(InvertedDisconnect, self).__init__(active_high=True, **kwargs)
        self.__name__ = "Disconnect(i)"
        
        
class InvertedUnloader(OnOff):
    """Extension of On/Off for Unloader accessory w/ inverted active_high."""
    def __init__(self, **kwargs) -> None:
        super(InvertedUnloader, self).__init__(active_high=True, **kwargs)
        self.__name__ = "Unloader(i)"


class SpurTrainSwitch(RelayTrainSwitch):
    """Extension of Relay Switch that will optionally depower the track."""
    def __init__(self, active_high: bool = False, **kwargs) -> None:
        super(SpurTrainSwitch, self).__init__(active_high=active_high, **kwargs)
        self.__name__ = 'Spur Train Switch'

    def _action(self, action: str) -> object:
        # leave the pins on in an alternating fashion
        conf = self.action_to_conf(action)

        if conf == 'br':
            self.yg_relay.off()
            self.br_relay.on()

        if conf == 'yg':
            self.br_relay.off()
            self.yg_relay.on()
        return conf


class InvertedSpurTrainSwitch(SpurTrainSwitch):
    """Extension of Spur Train Switch but with inverted active_high."""
    def __init__(self, **kwargs) -> None:
        super(InvertedSpurTrainSwitch, self).__init__(active_high=True, **kwargs)
        self.__name__ = 'Spur(i) Train Switch'


class InvertedRelayTrainSwitch(RelayTrainSwitch):
    """Extension of Relay Train Switch but with inverted active_high."""
    def __init__(self, **kwargs) -> None:
        super(InvertedRelayTrainSwitch, self).__init__(active_high=True, **kwargs)
        self.__name__ = 'Relay(i) Train Switch'


CLS_MAP = {
    'relay': RelayTrainSwitch,
    'servo': ServoTrainSwitch,
    'spur': SpurTrainSwitch,
    'spuri': InvertedSpurTrainSwitch,
    'relayi': InvertedRelayTrainSwitch,
    'Relay Train Switch': RelayTrainSwitch,
    'Servo Train Switch': ServoTrainSwitch,
    'Spur Train Switch': SpurTrainSwitch,
    'Spur(i) Train Switch': InvertedSpurTrainSwitch,
    'Relay(i) Train Switch': InvertedRelayTrainSwitch,
    'On/Off': OnOff,
    'onoff': OnOff,
    'Disconnect': Disconnect,
    'disconnect': Disconnect,
    'Unloader': Unloader,
    'unloader': Unloader,
    'Disconnect(i)': InvertedDisconnect,
    'disconnecti': InvertedDisconnect,
    'Unloader(i)': InvertedUnloader,
    'unloaderi': InvertedUnloader,
}
