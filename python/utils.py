"""Utility functions."""
import logging
import os

LOG_FILE = 'server.log'
WORKING_DIRECTORY = os.path.join('/', 'home', 'pi', 'Documents', 'trains')

class InvalidCurrentWorkingDirectory(Exception):
    """Raised when the current working directory (cwd) is incorrect."""
    pass

def check_working_directory() -> None:
    """Ensure cwd is /home/pi/Documents/trains"""
    cwd = os.getcwd()
    if cwd != WORKING_DIRECTORY:
        raise InvalidCurrentWorkingDirectory(
            "Expected current working directory (cwd) is: \n" +
            f"{WORKING_DIRECTORY} \n" + 
            "Found cwd: \n" +
            f"{cwd}"
        )

def setup_logging():
    """Sets up the server logging."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

def read_logs() -> str:
    """Reads logs from files."""
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()
    logs = ' '.join(lines).strip()
    return logs
