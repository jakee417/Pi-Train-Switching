import RPi.GPIO as GPIO
# import gpiozero
import time

# Set GPIO numbering mode
GPIO.setmode(GPIO.BOARD)

PULSE = 50  # default pulse value, 50Hz
SLEEP = 0.5  # default sleep time to prevent jitter


# Map an action to an angle
action_to_angle = {
    'left': 0.,
    'right': 90.
}

def angle_to_duty(angle: float):
    """Map a angle to a duty cycle"""
    return 2 + angle / 18


class TrainSwitch(object):
    def __init__(
        self,
        switch: int,
        pin: int,
        verbose: bool = False) -> None:
        """ Abstraction for a train switch.

        Args:
            switch: number for a physical switch on a train layout.
            pin: number for a gpio pin on a raspberry pi.
            verbose: Either True or False. Verbosity of object.
        """
        super().__init__()
        self.switch = switch
        self.pin = pin
        self.verbose = verbose
        self.state = None

        GPIO.setup(self.pin, GPIO.OUT)
        self.servo = GPIO.PWM(self.pin, PULSE)
        self.servo.start(0)
        if self.verbose:
            print(f"{self} is started...")

    def __repr__(self):
        return f"switch: {self.switch} @ pin: {self.pin}"

    def action(self, action: str) -> None:
        """ Execute an action on a train switch.

        Args:
            action: One of `left` or `right`
        """
        angle = action_to_angle.get(action)

        if isinstance(angle, type(None)):
            raise ValueError(
                "Invalid command to train switch." + 
                "\n Found action: {action}"
            )

        self.servo.ChangeDutyCycle(angle_to_duty(angle))
        time.sleep(SLEEP)
        self.servo.ChangeDutyCycle(0)

        if self.verbose:
            print(
                f"{self}: \n" +
                f"++++ state: {action} \n" +
                f"++++ angle: {angle})")

    def close(self) -> None:
        """Close a connection with a switch."""
        self.servo.stop()
        if self.verbose:
            print(f"{self} is closed...")
        GPIO.cleanup()
