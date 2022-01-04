# Control Lionel Switches with a Raspberry Pi Zero 2 W and Servos!

## GPIO Pins
The pins to use for this project are:
- 7
- 11
- 12
- 13
- 15
- 16
- 18
- 22

## Services
Since our project relies upon `pigpiod`, we start this daemon
```bash
sudo systemctl enable pigpiod
```
Now to start the train service, `train_switch.service`
```bash
cd /home/user/Pi-Train-Switching
sudo cp train_switch.service /etc/systemd/system/train_switch.service
sudo systemctl enable train_switch.service
```


## References
https://www.dexterindustries.com/Arduberry/example-projects-with-arduberry-and-raspberry-pi/lionel-train-switch-control-with-a-raspberry-pi-2/