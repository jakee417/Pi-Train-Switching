from RPi import GPIO
from gpiozero import AngularServo
import time
from abc import abstractmethod

PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter - half seconds

# Map an action to an angle
action_to_angle = {
    'left': 0.0,
    'right': 90.0
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
                    f"++++ initial state: {self.state} \n" +
                    f"++++ action: {action} \n" +
                    f"++++ angle: {angle})"
                )

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
        

class ManualTrainSwitch(BaseTrainSwitch):
    def __init__(self, **kwargs) -> None:
        """ Train switch wrapping the RPi.GPIO class for manual switches.
        
        We followed a great demo from youtuber `ExplainingComputers` to 
        implement our first Rasperry Pi GPIO Train Switch.

        References:
            https://www.explainingcomputers.com/pi_servos_video.html
        """
        super(ManualTrainSwitch, self).__init__(**kwargs)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.pin, PULSE)
        self.servo.start(0)

    @staticmethod
    def angle_to_duty(angle: float):
        """Map a angle to a duty cycle
        
        Notes:
            0 degrees: 2% duty cycle
            180 degrees: 12% duty cycle
        """
        return 2 + angle / 18

    def _action(self, angle: int) -> None:
        self.servo.ChangeDutyCycle(self.angle_to_duty(angle))
        time.sleep(SLEEP)  # wait to stop
        self.servo.ChangeDutyCycle(0)  # stop

    def _close(self) -> None:
        """Close a connection with a switch."""
        self.servo.stop()


class AngularServoTrainSwitch(BaseTrainSwitch):
    def __init__(self, **kwargs) -> None:
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
        self.servo = AngularServo(
            pin="BOARD" + str(self.pin),
            frame_width=1/PULSE,  # 50Hz corresponds to 20/1000s default
            min_pulse_width=1/1000,  # corresponds to 2% duty cycle
            max_pulse_width=2/1000  # correponds to 10% duty cycle
        )

    def _action(self, angle: int) -> None:
        self.servo.angle = angle

    def _close(self) -> None:
        self.servo.close()

class RelayTrainSwitch(BaseTrainSwitch):
    """Train switch using a Modular Relay
    
    References:
        https://www.electronicshub.org/control-a-relay-using-raspberry-pi/
    
    """
    pass
