"""Train switch classes"""

import time
from abc import abstractmethod
from typing import Union, Tuple


PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter - half seconds
BLINK = 0.25 # default time to wait between blinking

class BaseTrainSwitch:
    def __init__(
        self,
        pin: Union[int, Tuple[int, int]],
        logger: object = None) -> None:
        """ Abstract base class for a train switch.

        Args:
            pin: Unique number for a gpio pin on a raspberry pi.
                Alternatively a tuple of integers for multi-pin devices.
            verbose: Either True or False. Verbosity of object.
        """
        self.__name__ = 'Base Train Switch'
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
        if isinstance(self.__pin, int):
            return [self.__pin]
        else:
            return list(self.__pin)


    @property
    def state(self) -> str:
        """Returns the active state."""
        return self.__state

    @state.setter
    def state(self, state: str) -> None:
        self.__state = state

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
            'pin': self.pin,
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
        'Turn': 100.0,
        'Straight': 180.0
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
            action: One of `Straight` or `Turn`
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


class ServoTrainSwitch(BaseTrainSwitch):
    def __init__(
        self,
        min_angle: float = 100.,
        max_angle: float = 180.,
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
        from gpiozero.pins.pigpio import PiGPIOFactory
        from gpiozero import AngularServo
        super(ServoTrainSwitch, self).__init__(**kwargs)

        # gpiozero API expects "BOARD" in front of the pin #
        self.__name__ = 'Servo Train Switch'
        self.pin_name = "BOARD" + str(self.pin)
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
            pin_factory=PiGPIOFactory()
        )

        if self.logger:
            self.logger.info(f"++++ {self} is started...")

    def _action(self, action: str) -> object:
        angle = self.action_to_angle(action)
        self.servo.angle = angle
        return angle

    def __del__(self) -> None:
        self.servo.close()

class RelayTrainSwitch(BaseTrainSwitch):
    def __init__(self, **kwargs) -> None:
        """ Relay switch wrapping the gpiozero class for remote train switches.
        
        References:
            https://www.electronicshub.org/control-a-relay-using-raspberry-pi/

        Notes:
            The default pin factory for this device is:
            `gpio.zero.pins.pigpio.PiGPIOFactory`
            and cannot be mixed with other pin factories:
            https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
        
        """
        from gpiozero.pins.pigpio import PiGPIOFactory
        from gpiozero import DigitalOutputDevice
        super(RelayTrainSwitch, self).__init__(**kwargs)
        self.__name__ = 'Relay Train Switch'
        
        if not isinstance(self.pin, tuple):
            raise ValueError(f"Expecting multiple pins. Found {self.pin}")

        if len(self.pin) != 2:
            raise ValueError(f"Expecting two pins. Found {self.pin}")

        # when active_high=False, on() seems to pass voltage and off() seems to pass no voltage.
        # We initially set to False.
        self.yg_relay = DigitalOutputDevice(
            pin="BOARD" + str(self.pin[0]),
            active_high=False,
            initial_value=False,
            pin_factory=PiGPIOFactory()
        )
        self.br_relay = DigitalOutputDevice(
            pin="BOARD" + str(self.pin[1]),
            active_high=False,
            initial_value=False,
            pin_factory=PiGPIOFactory()
        )

        if self.logger:
            self.logger.info(f"++++ {self} is started...")

    @staticmethod
    def action_to_conf(action: str):
        """ Map an action to a relay configuration"""
        mapping = {
            'Turn': 'br',
            'Straight': 'yg',
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

CLS_MAP = {
	'relay': RelayTrainSwitch,
	'servo': ServoTrainSwitch,
	'Relay Train Switch': RelayTrainSwitch,
	'Servo Train Switch': ServoTrainSwitch
}
