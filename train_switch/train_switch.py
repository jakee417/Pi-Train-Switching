import RPi.GPIO as GPIO
import time
from gpiozero import AngularServo
from abc import abstractmethod

# Minimums and maximums for AngularServo
MIN_ANGLE = -42
MAX_ANGLE = 44

PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter

# Map an action to an angle
action_to_angle = {
    'left': 0.,
    'right': 90.
}


class BaseTrainSwitch:
    def __init__(
        self,
        switch: int,
        pin: int,
        verbose: bool = False) -> None:
        """ Abstract base class for a train switch.

        Args:
            switch: number for a physical switch on a train layout.
            pin: number for a gpio pin on a raspberry pi.
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

    @abstractmethod
    def _action(self, angle: int) -> None:
        pass
    
    def action(self, action: str) -> None:
        """ Execute an action on a train switch.

        Args:
            action: One of `left` or `right`
        """
        if self.state == action:
            print(
                f"{self}: \n" +
                f"++++ skipping {action} which matches state {self.state}"
            )
            return

        # convert the action to an angle value. ensure its not `None`.
        angle = action_to_angle.get(action)

        if isinstance(angle, type(None)):
            raise ValueError(
                "Invalid command to train switch." + 
                "\n Found action: {action}"
            )

        # complete derived class's work
        try:
            self._action(angle)

            if self.verbose:
                print(
                    f"{self}: \n" +
                    f"++++ initial state: {self.state}" +
                    f"++++ action: {action} \n" +
                    f"++++ angle: {angle})"
                )

            # remember new state
            self.state = action

        except Exception as ex:
            print(
                f"{self}: \n" +
                f"++++ exception raised: {e}"
            )

    @abstractmethod
    def _close(self) -> None:
        pass

    def close(self) -> None:
        """Close a connection with a switch."""
        self._close()
        
        if self.verbose:
            print(f"{self} is closed...")
        

class RPiGPIOTrainSwitch(BaseTrainSwitch):
    def __init__(self, **kwargs) -> None:
        """ Train switch wrapping the RPi.GPIO class
        
        References:
            https://www.explainingcomputers.com/pi_servos_video.html

        """
        super(RPiGPIOTrainSwitch, self).__init__(**kwargs)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.pin, PULSE)
        self.servo.start(0)

    @staticmethod
    def angle_to_duty(angle: float):
        """Map a angle to a duty cycle"""
        return 2 + angle / 18

    def _action(self, angle: int) -> None:
        self.servo.ChangeDutyCycle(self.angle_to_duty(angle))
        time.sleep(SLEEP)
        self.servo.ChangeDutyCycle(0)

    def _close(self) -> None:
        """Close a connection with a switch."""
        self.servo.stop()
        GPIO.cleanup()


class AngularServoTrainSwitch(BaseTrainSwitch):
    def __init__(
        self,
        min_angle: float = MIN_angle,
        max_angle: float = MAX_angle,
        initial_angle: float = 0.,
        **kwargs) -> None:
        """ Train switch wrapping the AngularServo class

        Args:
            min_angle: minimum angle of the angular servo
            max_angle: maximum angle of the angular servo
            initial_angle: intial angle of the servo

        References:
            https://gpiozero.readthedocs.io/en/stable/api_output.html#angularservo
            https://gpiozero.readthedocs.io/en/stable/recipes.html#servo
        """
        super(AngularServoTrainSwitch, self).__init__(**kwargs)

        self.initial_angle = intial_angle
        self.min_angle = min_angle
        self.max_angle = max_angle

        self.servo = AngularServo(
            pin=self.pin,
            initial_angle=self.initial_angle,
            min_angle=self.min_angle,
            MAX_ANGLE=self.max_angle,
        )

    def _action(self, angle: int) -> None:
        self.servo.angle = angle
        time.sleep(SLEEP)

    def _close(self) -> None:
        self.servo.close()

class RelayTrainSwitch(BaseTrainSwitch):
    """Train switch using a Modular Relay"""
    pass
