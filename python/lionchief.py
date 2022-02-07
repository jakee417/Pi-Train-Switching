from python import bluetooth
import time

PITCHES = [0xfe, 0xff, 0, 1, 2]

class LionChief(object):
    def __init__(self, mac_address: str, logger: object):
        """ API for LionChief train via a bluetooth connection.

        Args:
            mac_address: string representation of the mac address
                On a linux machine, this is commonly found by simply
                attempting a bluetooth connection and looking under
                `details`.
            logger: logging object passed from Flask server
        """
        self._mac_address = mac_address
        self._blue_connection = bluetooth.BTLEDevice(self._mac_address)
        self.current_speed = 0
        self.logger = logger

    @property
    def connected(self) -> bool:
        if self._blue_connection: return self._blue_connection._connected
        return False

    def connect(self, max_retries: int = 5) -> None:
        """Connects to a LionChief with a set number of retries."""
        self.logger.info(f"++++ Connecting LionChief @ {self._mac_address}...")
        i = 0
        while self.connected == False and i < max_retries:
            try:
                self._blue_connection.connect()
            except Exception as e:
                self.logger.error(
                    f"++++ Error while connecting ({i + 1} of {max_retries}): \n"
                    f"{e}"
                )
            i += 1

        if self.connected == False:
            self.logger.error("++++ Could not connect with Lionchief...")

    def _send_cmd(self, values: list) -> bool:
        """Core send command,only functions when connected. Returns success boolean."""
        if self.connected:
            checksum = 256
            for v in values:
                checksum -= v
            while checksum < 0:
                checksum += 256
            values.insert(0, 0)
            values.append(checksum)
            self._blue_connection.char_write(0x25, bytes(values), True)
            return True
        return False

    def _set_speed(self, speed: int) -> None:
        if self._send_cmd([0x45, speed]):
            self.current_speed = speed
            self.logger.info(f"++++ Speed: {self.current_speed}...")

    #########################################################################
    # "Action" functions
    #########################################################################
    def ramp(self, end_speed: int) -> None:
        """Ramp up speed while ringing the bell."""
        # TODO: Add momentum
        self.set_bell(True)
        self.logger.info("++++ Starting ramp...")
        speed = self.current_speed
        while speed != end_speed:
            self._set_speed(speed)
            if speed > end_speed:
                speed -= 1
            else:
                speed += 1
            time.sleep(.5)
        self._set_speed(end_speed)
        self.set_bell(False)

    def speak(self, phrase: int = 0) -> None:
        self._send_cmd([0x4d, phrase, 0])

    def horn(self, honk_time: int = 1) -> None:
        self.set_horn(True)
        time.sleep(honk_time)
        self.set_horn(False)

    def horn_seq(self, seq: str) -> None:
        """Mimic horn sequences found on most common train whistles.
        
        Args:
            seq: One of ' ', '-', and '.' that map to different sounds.
        """
        for s in seq:
            if s == '-':
                self.horn(1)
            elif s == '.':
                self.horn(0.5)
            elif s == ' ':
                time.sleep(0.5)

    def set_horn(self, on: bool) -> None:
        self._send_cmd([0x48, 1 if on else 0])

    def set_bell(self, on: bool) -> None:
        self._send_cmd([0x47, 1 if on else 0])

    def set_reverse(self, on: bool) -> None:
        self._send_cmd([0x46, 0x02 if on else 0x01])   

    def set_over_volume(self, volume: int) -> None:
        self._send_cmd([0x4c, volume])

    def set_bell_volume(self, volume: int) -> None:
        self._send_cmd([0x44, 0x02, volume])

    def set_horn_volume(self, volume: int) -> None:
        self._send_cmd([0x44, 0x01, volume])

    def set_speech_volume(self, volume: int) -> None:
        self._send_cmd([0x44, 0x03, volume])

    def set_engine_volume(self, volume: int) -> None:
        self._send_cmd([0x44, 0x04, volume])

    def set_bell_pitch(self, pitch: int) -> None:
        if pitch < 0 or pitch >= len(PITCHES):
            self.logger.error(f"++++ Bell pitch should be between 0 and {len(PITCHES)}")
            return
        self._send_cmd([0x44, 0x02, 0x0e, PITCHES[pitch]])

    def set_horn_pitch(self, pitch: int) -> None:
        if pitch < 0 or pitch >= len(PITCHES):
            self.logger.error(f"++++ Horn pitch should be between 0 and {len(PITCHES)}")
            return
        self._send_cmd([0x44, 0x01, 0x0e, PITCHES[pitch]])  

    def close(self, max_retries: int = 5) -> None:
        # TODO: Not working, figure out way to kill all threads to reconnect
        # Attempt to close the bluetooth connection
        i = 0
        while self.connected and i < max_retries:
            try:
                self._blue_connection.stop()
                # self.logger.info(f"++++ Device Removal: \n {bluetooth.close_device(self._mac_address)}")
            except Exception as e:
                self.logger.info(f"++++ Closing connection ({i + 1} of {max_retries})")
        assert self.connected == False

    def __del__(self):
        self.close()


# if __name__ == "__main__":
#     logging.getLogger().setLevel(logging.INFO)
#     chief = LionChief("34:14:B5:3E:A4:71", logging)
#     chief.connect()
#     time.sleep(1)
#     chief.ramp(10)
#     chief.horn_seq(' . . ')
#     time.sleep(8)
#     chief.speak()
#     time.sleep(8)
#     chief.ramp(0)
#     chief.horn_seq(' . ')
#     chief.close()
