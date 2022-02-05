#!/usr/bin/env python

"""
bluetooth.py
============
Python wrapper for gatttool, to allow programmatic control of Bluetooth LE
devices from within Python.
Much of the gatttool interface is borrowed from the gatttool backend of
https://github.com/stratosinc/pygatt, which is distributed under an Apache
2.0 license: http://www.apache.org/licenses/LICENSE-2.0
Credit to the following:
Jeff Rowberg @jrowberg https://github.com/jrowberg/bglib
Greg Albrecht @ampledata https://github.com/ampledata/pygatt
Christopher Peplin @peplin https://github.com/stratosinc/pygatt
Morten Kjaergaard @mkjaergaard https://github.com/mkjaergaard/pygatt
Michael Saunby @msaunby https://github.com/msaunby/ble-sensor-pi
Steven Sloboda sloboste@umich.edu https://github.com/sloboste
"""

# Standard libary
from collections import defaultdict
import threading
import string
import time
import re
import subprocess

# Third party
import pexpect

__author__ = 'Blaine Rogers <blaine.rogers@imgtec.com>'
__credits__ = ['Jeff Rowberg', 'Greg Albrecht', 'Christopher Peplin',
'Morten Kjaergaard', 'Michael Saunby', 'Steven Sloboda']

class BluetoothLEError(Exception):
    """Parent exception class for Bluetooth interface"""
    def __repr__(self):
        return '<%s, %s>' % (self.__class__.__name__, self.message)

class NotConnectedError(BluetoothLEError):
    pass

class NotificationTimeout(BluetoothLEError):
    pass

class NoResponseError(BluetoothLEError):
    pass


class BTLEDevice(object):
    """Wrapper for gatttool session with bluetooth peripheral"""
    DEFAULT_CONNECT_TIMEOUT=3.0

    def __init__(self, mac_address, hci_device='hci0'):
        """Initialises the device.
        Sets up threading for the notification listener and starts the
        gatttool session.
        Args:
            mac_address (str): The mac address of the BLE device to connect
                to in the format "XX:XX:XX:XX:XX:XX"
            hci_device (str): The hci device to use with gatttool
        Raises:
            pexpect.TIMEOUT: If, for some reason, pexpect fails to spawn a 
                gatttool instance (e.g. you don't have gatttool installed).
        """
        ##### Internal state #####
        self._address = mac_address
        self._handles = {}               # Used for tracking which handles
        self._subscribed_handlers = {}   # have subscribed callbacks
        self._callbacks = defaultdict(set)
        self._lock = threading.Lock()
        self._connection_lock = threading.RLock()
        self._running = True
        self._thread = None
        self._con = None                 # The gatttool instance
        self._connected = False

        ##### Set up gatttool #####
        gatttool_cmd = ' '.join(
            ['gatttool',
             '-b', self._address,
             '-i', hci_device,
             '-I']
        )

        self._con = pexpect.spawn(gatttool_cmd, ignore_sighup=False)
        self._con.expect(r'\[LE\]>', timeout=1)

        ##### Start notification listener thread #####
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def char_read_hnd(self, handle):
        """Reads a characteristic by handle.
        Args:
            handle (int): The handle of the characteristic to read.
        Returns:
            bytearray: The value of the characteristic.
        Raises:
            NotConnectedError: If no connection to the device has been 
                established.
            NotificationTimeout: If the device is connected, but reading
                fails for another reason.
        """
        if not self._connected:
            message = 'device is not connected'
            raise NotConnectedError(message)

        with self._connection_lock:
            self._con.sendline('char-read-hnd %04x' % handle)
            self._expect(r'descriptor: .*?\r')
            rval = self._con.after.split()[1:]
            return bytearray([int(x, 16) for x in rval])

    def char_write(self, handle, value, wait_for_response=False):
        """Writes a value to a given characteristic handle.
        Args:
            handle (int): The handle to write to
            value (bytearray): The value to write
            wait_for_response (bool): If true, waits for a response from
                the peripheral to check that the value was written succesfully. 
        Raises:
            NotConnectedError: If no connection to the device has been
                established.
            NoResponseError: If `wait_for_response` is True and no write
                confirmation was received from the peripheral.
        """
        if not self._connected:
            message = 'device is not connected'
            raise NotConnectedError(message)

        suffix = 'req' if wait_for_response else 'cmd'
        value_string = ''.join('%02x' % byte for byte in value)
        command = 'char-write-%s %04x %s' % (suffix, handle, value_string)

        self._con.sendline(command)

        if wait_for_response:
            try:
                self._expect('Characteristic value was written successfully')
            except NotificationTimeout:
                message = 'no response received'
                raise NoResponseError(message)

    def connect(self, timeout=DEFAULT_CONNECT_TIMEOUT):
        """Established a connection with the device. 
        If connection fails, try running an LE scan first. 
        Args:
            timeout (numeric): Time in seconds to wait before giving up on
                trying to connect.
        Raises:
            NotConnectedError: If connection to the device fails.
        """
        try:
            self._con.sendline('connect')
            self._con.expect(r'Connection successful.*\[LE\]>', timeout)
            self._connected = True
            if not self._running:
                self._thread.run()
        except pexpect.TIMEOUT:
            self.stop()
            message = ('timed out after connecting to %s after %f seconds.'
                       % (self._address, timeout))
            raise NotConnectedError(message)

    def run(self):
        """Listens for notifications.  """
        while self._running:
            with self._connection_lock:
                try:
                    self._expect('nonsense value foobar', timeout=0.1)
                except NotificationTimeout:
                    pass
                except (NotConnectedError, pexpect.EOF):
                    break
            time.sleep(0.05)  # Stop thread from hogging _connection_lock

    def stop(self):
        """Stops the gatttool instance and listener thread.  """
        self._running = False  # stop the listener thread
        if self._con.isalive():
            self._con.sendline('exit')

            # wait one second for gatttool to stop
            for i in range(100):
                if not self._con.isalive(): break
                time.sleep(0.01)

            self._con.close()  # make sure gatttool is dead
            self._connected = False

    def subscribe(self, handle, callback=None, type_=0):
        """Subscribes to notification/indiciatons from a characteristic.
        This is achieved by writing to the control handle, which is assumed
        to be `handle`+1. If indications are requested and we are already
        subscribed to notifications (or vice versa), we write 0300 
        (signifying we want to enable both). Otherwise, we write 0100 for
        notifications or 0200 for indications.
        Args:
            handle (int): The handle to listen for.
            callback (f(int, bytearray)): A function that will be called
                when the notif/indication is received. When called, it will be
                passed the handle and value.
            type_ (int): If 0, requests notifications. If 1, requests 
                indications. If 2, requests both. Any other value will
                result in a ValueError being raised. 
        Raises:
            NoResponseError: If writing to the control handle fails.
            ValueError: If `type_` is not in {0, 1, 2}.
        """
        if type_ not in {0, 1, 2}:
            message = ('Type must be 0 (notifications), 1 (indications), or'
                       '2 (both).')
            raise ValueError(message)

        control_handle = handle + 1
        this, other = \
                (bytearray([1,0]), bytearray([2,0])) if _type == 0 else \
                (bytearray([2,0]), bytearray([1,0])) if _type == 1 else \
                (bytearray([3,0]), bytearray([3,0]))
        both = bytearray([3,0])

        with self._lock:
            if callback is not None:
                self._callbacks[handle].add(callback)

            previous = self._subscribed_handlers.get(handle, None)
            if not previous in [this, both]:
                write = both if previous == other else this
                self.char_write(control_handle, write, wait_for_response=True)
                self._subscribed_handlers[handle] = write

    def unsubscribe(self, handle, callback=None):
        """Unsubscribes from notif/indications on a handle.
        Writes 0000 to the control handle, which is assumed to be `handle`+1.
        If `callback` is supplied, removes `callback` from the list of
        callbacks for this handle.
        Args:
            handle (int): The handle to unsubscribe from.
            callback (f(int, bytearray)): The callback to remove,
                previously passed as the `callback` parameter of
                self.subscribe(handle, callback).
        Raises:
            NotificationTimeout: If writing to the control handle fails.
        """
        control_handle = handle + 1
        value = bytearray([0,0])
        with self._lock:
            if callback is not None:
                self._callbacks[handle].remove(callback)

            if self._subscribed_handlers.get(handle, None) != value:
                self.char_write(control_handle, value, wait_for_response=True)
                self._subscribed_handlers[handle] = value

    def _expect(self, expected, timeout=DEFAULT_CONNECT_TIMEOUT):
        """Searches for notif/indications while expecting a pattern.
        We may (and often do) get an indication/notification before a write
        completes, and so it can be lost if we "expect()"ed something that
        cam after it in the output, e.g.:
            > char-write-req 0x1 0x2
            Notification handle: xxx
            Write completed succesfully.
            >
        Anytime we expect() something we have to expect() notif/indications
        first for a short time.
        Args:
            expected (str): The pattern to search for in the output.
            timout (numeric): The time in seconds to wait before assuming the
                pattern will never be found.
        Raises:
            NotificationTimout: If the pattern is not found before the
                timeout is reached.
        """
        with self._connection_lock:
            patterns = [
                expected,
                'Notification handle = .*? \r',
                'Indication   handle = .*? \r',
                '.*Invalid file descriptor.*',
                '.*Disconnected\r'
            ]
            while True:
                try:
                    matched_pattern_index = self._con.expect(patterns, timeout)
                    if matched_pattern_index == 0:
                        break
                    elif matched_pattern_index in {1, 2}:
                        self._handle_notification(self._con.after)
                    elif matched_pattern_index in {3, 4}:
                        message = ''
                        if self._running:
                            message = 'unexpectedly disconnected'
                            self._running = False
                        raise NotConnectedError(message)
                except pexpect.TIMEOUT:
                    message = 'timed out waiting for a notification'
                    raise NotificationTimeout(message)

    def _handle_notification(self, msg):
        """Handle a notification from the device.
        Propagates the handle and value to all registered callbacks.
        Args:
            msg (str): The notification message, which looks like these:
                    Notification handle = <handle> value: <value> 
                    Indication   handle = <handle> value: <value>
        """
        hex_handle, _, hex_value = string.split(msg.strip(), maxsplit=5)[3:]
        handle = int(hex_handle, 16)
        value = bytearray.fromhex(hex_value)

        with self._lock:
            if handle in self._callbacks:
                for callback in self._callbacks[handle]:
                    callback(handle, value)

    def __enter__(self):
        return self

    def __exit__(self):
        if self._con.isalive():
            self.stop()

def le_scan(sudo_password=None, timeout=5):
    """Performs a BTLE scan.
    If you don't want to use sudo, you must allow normal users to perform
    LE scanning:
        setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
    Args:
        sudo_password (str): The password for super user priveleges. Do not
            hard code this! Fetch it from the user, then destroy it asap.
            If `None`, sudo priveleges will be assumed.
        timeout (numeric): Time (in seconds) to wait for the scan to complete
        use_sudo (bool): If True, performs scan as superuser.
    Returns:
        [{str:str}]: A list of dictionaries, each of which represents a
        device. The dictionaries have two keys, 'address' and 'name',
        whose values are the MAC address and name of the device
        respectively.
        [{'address': device_1_address, 'name': device_1_name},
         {'address': device_2_address, 'name': device_2_name},
         ...
         {'address': device_n_address, 'name': device_n_name}]
    Raises:
        BluetoothLEError: If hcitool exits before the timeout.
    """
    command = 'hcitool lescan'
    if sudo_password: command = 'sudo %s' % command

    scan = pexpect.spawn('bash', ['-c', command], ignore_sighup=False)
    if sudo_password: 
        scan.sendline(sudo_password)
        scan.readline()  # exclude sudo message from scan.before

    try:
        # Not actually expecting anything, just using the convenient timeout
        scan.expect('nonsense value foobar', timeout=timeout)
    except pexpect.EOF:
        message = 'unexpected error while scanning: \n' + scan.before
        if 'Input/Output error' in scan.before:
            message += '\n - Try resetting the bluetooth controller.'
        elif 'Operation not permitted' in scan.before:
            message += '\n - Try running using sudo.'
        raise BluetoothLEError(message)
    except pexpect.TIMEOUT:
        devices = {}
        for line in scan.before.split('\r\n'):
            match = re.match(r'(([0-9A-Fa-f]{2}:?){6}) (\(?\w+\)?', line)
            if match is not None:
                address = match.group(1)
                name = match.group(3)
                if name == '(unknown)': name = None
                if address in devices:
                    if devices[address]['name'] is None and name is not None:
                        devices[address]['name'] = name
                else:
                    devices[address] = {'address': address, 'name': name}
        # Convert from dict_values([{str:str}]) to [{str:str}]
        return [device for device in devices.values()]
    finally:
        # try our best to kill sudo
        scan.sendcontrol('c'); scan.sendcontrol('x'); scan.sendcontrol('d');
        scan.close()

    return []  # failsafe


def reset_bluetooth_controller(sudo_password=None, hci_device='hci0', 
                               timeout=3.0):
    """ Reinitialises the bluetooth controller interface.
    This is accomplished by bringing down and up the interface using
    hciconfig. This requires superuser priveleges.
    Args:
        sudo_password (str): The password for super user priveleges. Do not
            hard code this! Fetch it from the user, then destroy it asap.
            If `None`, sudo priveleges will be assumed.
        hci_device (str): The interface to reinitialise.
        timeout (numeric): Time to wait before abandoning hope.
    Raises:
        BluetoothLEError: If hciconfig fails or the timeout is reached.
    """
    command = 'hciconfig %s reset' % hci_device
    if sudo_password: command = 'sudo %s' % command

    p = pexpect.spawn('bash', ['-c', command], ignore_sighup=False)
    if sudo_password: p.sendline(sudo_password)

    try:
        p.expect('nonsense value foobar', timeout=timeout)
    except pexpect.EOF:
        p.close()
        if p.exitstatus != 0:
            message = 'hciconfig failed: \n' + p.before
            if 'Operation not permitted' in p.before:
                message += '\n - Try running using sudo.'
            raise BluetoothLEError(message)
    except pexpect.TIMEOUT:
        # try our best to kill sudo
        p.sendcontrol('c'); p.sendcontrol('x'); p.sendcontrol('d');
        message = 'hciconfig did not complete before timeout'
        raise BluetoothLEError(message)
    finally:
        p.close()

def show_all_devices() -> str:
    return subprocess.check_output(
        """
        bluetoothctl devices | \
        cut -f2 -d' ' | \
        while read uuid; do bluetoothctl info $uuid; done| \
        grep -e \"Device\|Connected\|Name\"
        """,
        shell=True
    )\
    .decode("utf-8")

def close_device(mac: str) -> str:
    return subprocess.check_output(
        f"bluetoothctl disconnect {mac}",
        shell=True
    )\
    .decode("utf-8")

if __name__ == "__main__":
    # Run as bluetoothctl python wrapper to show all devices
    print(show_all_devices())