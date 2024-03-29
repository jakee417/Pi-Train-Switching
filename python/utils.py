"""Utility functions."""
import logging
import os
import getpass
import subprocess
import pickle
from typing import Union, Tuple, Optional, List, Dict
from collections import OrderedDict

from python.train_switch import CLS_MAP

LOG_FILE = 'server.log'
PICKLE_PATH = './profiles/'

DEFAULT_PATH = os.path.join(
	PICKLE_PATH, 'cfg.pkl'
)
WORKING_DIRECTORY = os.path.join(
    '/', 'home', getpass.getuser(), 'Pi-Train-Switching'
)

# Grab the pinout stdout
PINOUT = subprocess.check_output('pinout --monochrome', shell=True)\
    .decode("utf-8") \
    .replace(' ', '&nbsp;')

# For reference only.
"""
J8:
   3V3  (1) (2)  5V    
 GPIO2  (3) (4)  5V    
 GPIO3  (5) (6)  GND   
 GPIO4  (7) (8)  GPIO14
   GND  (9) (10) GPIO15
GPIO17 (11) (12) GPIO18
GPIO27 (13) (14) GND   
GPIO22 (15) (16) GPIO23
   3V3 (17) (18) GPIO24
GPIO10 (19) (20) GND   
 GPIO9 (21) (22) GPIO25
GPIO11 (23) (24) GPIO8 
   GND (25) (26) GPIO7 
 GPIO0 (27) (28) GPIO1 
 GPIO5 (29) (30) GND   
 GPIO6 (31) (32) GPIO12
GPIO13 (33) (34) GND   
GPIO19 (35) (36) GPIO16
GPIO26 (37) (38) GPIO20
   GND (39) (40) GPIO21
"""

GPIO_PINS = set(
    [
        3, 
        5, 
        7, 8,
            10,
        11, 12, 
        13, 
        15, 16,
            18,
        19,
        21, 22,
        23, 24,
            26,

        29,
        31, 32,
        33, 
        35, 36,
        37, 38,
            40
    ]
)

def sort_pool(pool: list) -> list:
    l = list(pool)
    l.sort()
    return l

class InvalidCurrentWorkingDirectory(Exception):
    """Raised when the current working directory (cwd) is incorrect."""
    pass

class PinNotInPinPool(Exception):
    """Raised when a pin is accessed that is not available for use."""
    pass

def check_working_directory() -> None:
    """Ensure cwd is /home/pi/Documents/trains"""
    cwd = os.getcwd()
    if cwd != WORKING_DIRECTORY:
        logging.warning(
            "Expected current working directory (cwd) is: \n" +
            f"{WORKING_DIRECTORY} \n" + 
            "Found cwd: \n" +
            f"{cwd}"
        )

def setup_logging() -> None:
    """Sets up the server logging."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

def read_logs() -> str:
    """Reads logs from file in reverse order."""
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()
    lines.reverse()
    logs = '\n'.join(lines)
    return logs

def devices_to_dict(devices: OrderedDict) -> OrderedDict:
    """Returns a serializiable {str(pins): str(device)} mapping of devices."""
    return OrderedDict({
        str(pin): d.to_json()
        for pin, d in devices.items()
    })

def api_return_dict(devices: OrderedDict) -> dict:
    """Returns a json-returnable dict for an API call."""
    devices = devices_to_dict(devices)
    return {
        "devices": list(devices.values())
    }

def ios_return_dict(devices: OrderedDict, pin_pool: list, device_types: List[str]) -> dict:
    """Returns a json-returnable dict for an iOS call."""
    devices = devices_to_dict(devices)
    return {
        "devices": list(devices.values()),
        "pin_pool": pin_pool,
        #"device_types": device_types,
	    "profiles": get_all_profiles()
    }

def save_cfg(devices: OrderedDict, name: str = DEFAULT_PATH) -> str:
    """Save and return a serialized message."""
    message = None
    try:
        # serialize a cfg.
        cfg = devices_to_dict(devices)
        pickle.dump(cfg, open(name, 'wb'))
        message = "Saved Configuration."
    except Exception as e:
        message = e
    return message

def construct_from_cfg(cfg: OrderedDict, logger: object) -> OrderedDict:
    """Constructs a new dictionary of devices from a configuration."""
    # construct switches from config
    devices = OrderedDict({
        str(v['pins']): CLS_MAP.get(v['name'])(
            pin=v['pins'], logger=logger
        ) for _, v in cfg.items()
	})
    # Set states from configuration
    _ = [v.action(cfg[str(p)]['state']) for p, v in devices.items()]
    return devices

def load_cfg(path: str) -> Tuple[Optional[OrderedDict], Optional[str]]:
    """Load a cfg from a path. Return device dictionary and string message."""
    cfg = None
    message = None
    if not os.path.exists(path):
        message = "No configuration to load."
    else:
        # read a configuration
        cfg = pickle.load(open(path, 'rb'))
        message = "Loaded file."
    return cfg, message

def remove_cfg(path: str) -> Optional[str]:
    """Remove a cfg from a path. Return string message."""  
    message = None
    if not os.path.exists(path):
        message = "No configuration to remove."
    else:
        # remove a configuration
        os.remove(path)
        message = "Removed file."
    return message


def close_devices(devices: OrderedDict) -> None:
    """Close all connections in a dictionary of devices."""
    # close all pre existing connections
    for _, device in devices.items():
        device.close()

    del devices  # garbage collect

def update_pin_pool(devices: OrderedDict) -> set:
    """Update a pool of pins based off current devices."""
    pin_pool = GPIO_PINS.copy()
    for _, d in devices.items():
        for p in d.pin_list:
            if p not in pin_pool:
                raise PinNotInPinPool(
                    f"pin {p}, {type(p)} was not in pin pool: {pin_pool}."
                )
            pin_pool.remove(p)
    return pin_pool

def custom_pinout(
    pin_pool: set,
    total_pins: int = 40,
    pinout: str = PINOUT) -> str:
    """Custom update to the `pinout` program by highlighting unused pins."""
    all_pins = set(list(range(1, 41)))
    replace_pins = all_pins - pin_pool

    for pin in pin_pool:
        find_text = "(" + str(pin) + ")"
        replace = f"<mark>{find_text}</mark>"
        pinout = pinout.replace(find_text, replace)

    pinout = "<mark>(pin)</mark> is available. \n" + pinout
    return pinout

def convert_csv_tuples(inputs: str) -> Union[int, tuple]:
        """Converts a comma seperated list of pins into a python object."""
        inputs = inputs.split(',')
        inputs = [int(input) for input in inputs]
        inputs.sort()
        return tuple(inputs)

def get_all_profiles() -> List[str]:
    """Gets all of the profile names without file extension."""
    os.makedirs(PICKLE_PATH, exist_ok=True)
    profiles = os.listdir(PICKLE_PATH)
    profiles = [i.split('.')[0] for i in profiles]
    profiles.sort()
    return profiles
