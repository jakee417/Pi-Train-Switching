"""Train switch classes"""

import time
from abc import abstractmethod


PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter - half seconds

# Map an action to an angle
action_to_angle = {
    'turn': 100.0,
    'straight': 180.0
}


class BaseTrainSwitch:
    def __init__(
        self,
        switch: int,
        pin: int,
        verbose: bool = False) -> None:
        """ Abstract base class for a train switch.

        Args:
            switch: Unique number for a physical switch on a train layout.
            pin: Unique number for a gpio pin on a raspberry pi.
            verbose: Either True or False. Verbosity of object.
        """
        self.switch = switch
        self.pin = pin
        self.verbose = verbose
        self.state = None
        self.servo = None
        if self.verbose:
            print(f"{self} is started...")

    def __repr__(self):
        return f"switch: {self.switch} @ pin: {self.pin}"

    def print_update(
        self, 
        initial_state: str, 
        action: str, 
        angle: object) -> None:
        """Prints update message"""
        if self.verbose:
            print(
                f"{self}: \n" +
                f"++++ initial state: {initial_state} \n" +
                f"++++ action: {action} \n" +
                f"++++ angle update: {angle}"
            )

    @abstractmethod
    def _action(self, angle: int) -> None:
        pass
    
    def action(self, action: str) -> None:
        """ Execute an action on a train switch.

        If an ordered action is the same as the previous state, then do nothing.
        Otherwise, convert the action to an angle and perform an update to the
        state of the train switch.

        Args:
            action: One of `left` or `right`
        """
        if self.state == action:
            self.print_update(self.state, action, 'skipped')
            return

        # convert the action to an angle value. ensure it is not `None`.
        angle = action_to_angle.get(action)

        if isinstance(angle, type(None)):
            raise ValueError(
                "Invalid command to train switch." + 
                f"\n Found action: {action}"
            )

        # complete derived class's work
        try:
            self._action(angle)
            self.print_update(self.state, action, angle)

            # remember new state to check against future actions
            self.state = action

        except Exception as ex:
            print(
                f"{self}: \n" +
                f"++++ exception raised: {ex}"
            )

    @abstractmethod
    def _close(self) -> None:
        pass

    def close(self) -> None:
        """Close a connection with a switch."""
        self._close()
        
        if self.verbose:
            print(f"{self} is closed...")
        

class GPIOManualTrainSwitch(BaseTrainSwitch):
    def __init__(self, **kwargs) -> None:
        """ Servo class wrapping the RPi.GPIO class for manual train switches.
        
        We followed a great demo from youtuber `ExplainingComputers` to 
        implement our first Rasperry Pi GPIO Train Switch.

        References:
            https://www.explainingcomputers.com/pi_servos_video.html

        Notes:
            The default pin factory for this device is:
            `RPi.GPIO`
            and cannot be mixed with other pin factories:
            https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
        """
        from RPi import GPIO
        super(GPIOManualTrainSwitch, self).__init__(**kwargs)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.pin, PULSE)
        self.servo.start(0)

    @staticmethod
    def angle_to_duty(angle: float):
        """Map a angle to a duty cycle
        
        Notes:
            0°: 2% duty cycle
            180°: 12% duty cycle
        """
        return 2 + angle / 18

    def _action(self, angle: int) -> None:
        self.servo.ChangeDutyCycle(self.angle_to_duty(angle))
        time.sleep(SLEEP)  # wait to stop
        self.servo.ChangeDutyCycle(0)  # stop

    def _close(self) -> None:
        """Close a connection with a switch."""
        self.servo.stop()


class GPIOZeroManualTrainSwitch(BaseTrainSwitch):
    def __init__(
        self,
        min_angle: float = 0.,
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
        super(GPIOZeroManualTrainSwitch, self).__init__(**kwargs)

        # AngularServo API expects "BOARD" in front of the pin #
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

    def _action(self, angle: int) -> None:
        self.servo.angle = angle

    def _close(self) -> None:
        self.servo.close()

class RelayTrainSwitch(BaseTrainSwitch):
    """ Relay switch wrapping the gpiozero class for remote train switches.
    
    References:
        https://www.electronicshub.org/control-a-relay-using-raspberry-pi/

    Notes:
        The default pin factory for this device is:
        `gpio.zero.pins.pigpio.PiGPIOFactory`
        and cannot be mixed with other pin factories:
        https://gpiozero.readthedocs.io/en/stable/api_pins.html#changing-the-pin-factory
    
    """
    pass
