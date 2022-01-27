# Control Lionel Switches with a Raspberry Pi Zero 2 W and Servos!
This project demonstrates how to control Lionel Train Switches from a Raspberry Pi (`RPi`).

![Diagram](./static/diagram.jpg)

## Necessary Hardware
[Lionel Manual Switches](http://www.lionel.com/products/fastrack-o36-manual-switch-right-hand-6-12018/)
- [SG-90 Servo](https://www.amazon.com/Micro-Servos-Helicopter-Airplane-Controls/dp/B07MLR1498/ref=sr_1_1_sspa?crid=1R024DTWR7UM1&keywords=SG90+servo&qid=1641540462&sprefix=sg90+servo%2Caps%2C124&sr=8-1-spons&psc=1&spLa=ZW5jcnlwdGVkUXVhbGlmaWVyPUFaUjlQT1Q5UEgzQjAmZW5jcnlwdGVkSWQ9QTA3NzcxNTBMRlhKM1pNTzVYWkgmZW5jcnlwdGVkQWRJZD1BMDY1ODY0NjJVQVo1UVpWWjNQOVQmd2lkZ2V0TmFtZT1zcF9hdGYmYWN0aW9uPWNsaWNrUmVkaXJlY3QmZG9Ob3RMb2dDbGljaz10cnVl)
- [Female to female Jumper Cables
](https://www.amazon.com/EDGELEC-Breadboard-Optional-Assorted-Multicolored/dp/B07GD2BWPY/ref=sr_1_2_sspa?keywords=edgelec+120pcs+breadboard+jumper+wires&qid=1641540430&sprefix=EDGELEC+%2Caps%2C128&sr=8-2-spons&psc=1&spLa=ZW5jcnlwdGVkUXVhbGlmaWVyPUEzQUlVRkxCOTRZTzROJmVuY3J5cHRlZElkPUEwNTcxMzM4M0czSzhEQ1QyV0FSWCZlbmNyeXB0ZWRBZElkPUEwNDMxMzE5MlUwTkxJNUdHODJCVSZ3aWRnZXROYW1lPXNwX2F0ZiZhY3Rpb249Y2xpY2tSZWRpcmVjdCZkb05vdExvZ0NsaWNrPXRydWU=)

or

[Lionel Remote Switches](http://www.lionel.com/products/fastrack-o36-remote-switch-right-hand-6-12046/)
- [5V 2-Channel Relay Interface](https://www.amazon.com/SainSmart-101-70-100-2-Channel-Relay-Module/dp/B0057OC6D8/ref=sr_1_1?keywords=sainsmart+2-channel&qid=1641540392&sr=8-1)
- [Male to Female Jumper Cables](https://www.amazon.com/EDGELEC-Breadboard-Optional-Assorted-Multicolored/dp/B07GD2BWPY/ref=sr_1_2_sspa?keywords=edgelec+120pcs+breadboard+jumper+wires&qid=1641540430&sprefix=EDGELEC+%2Caps%2C128&sr=8-2-spons&psc=1&spLa=ZW5jcnlwdGVkUXVhbGlmaWVyPUEzQUlVRkxCOTRZTzROJmVuY3J5cHRlZElkPUEwNTcxMzM4M0czSzhEQ1QyV0FSWCZlbmNyeXB0ZWRBZElkPUEwNDMxMzE5MlUwTkxJNUdHODJCVSZ3aWRnZXROYW1lPXNwX2F0ZiZhY3Rpb249Y2xpY2tSZWRpcmVjdCZkb05vdExvZ0NsaWNrPXRydWU=)
- [22 Gauge Solid Wire Hookup Wires](https://www.amazon.com/Gauge-Wire-Solid-Hookup-Wires/dp/B088KQFHV7/ref=sr_1_2?crid=3RJFP5R14PQE&keywords=22+gauge+solid+wire+hookup+wire&qid=1641540503&sprefix=sg90+servo%2Caps%2C127&sr=8-2)


## Hardware Setup
**Lionel Manual Switches**
- [Connecting SG-90 Servo to `RPi`](https://youtu.be/xHDT4CwjUQE?t=323)
- TODO: Setup for building clay structures

**Lionel Remote Switches**
- [Connecting remote switch to the control relay remote switch](https://www.dexterindustries.com/Arduberry/example-projects-with-arduberry-and-raspberry-pi/lionel-train-switch-control-with-a-raspberry-pi-2/)
- [Connecting `RPi` to control relay](https://www.electronicshub.org/control-a-relay-using-raspberry-pi/)
- TODO: Include a simplified wiring schematic
## System Services
Since our project relies upon the `pigpiod` pin factory, start this [daemon](https://en.wikipedia.org/wiki/Daemon_(computing)):
```bash
sudo systemctl enable pigpiod
```

## Installation
```bash
cd ~
git clone https://github.com/jakee417/Pi-Train-Switching.git
cd Pi-Train-Switching
# Now run the setup helper
./setup.sh
```
A successful installation looks like:
```bash
pi@raspberrypi:~/Pi-Train-Switching $ ./setup.sh 
++++ Setting up train_switch.service in: /home/pi/.config/systemd/user
++++ Enabling train_switch.service
++++ Starting train_switch.service
++++ train_switch.service status:
● train_switch.service - Train Switch
     Loaded: loaded (/home/pi/.config/systemd/user/train_switch.service; enabled; vendor preset: enabled)
     Active: active (running) since Sat 2022-01-15 20:55:46 HST; 9min ago
   Main PID: 8522 (python3)
      Tasks: 5 (limit: 409)
        CPU: 3.658s
     CGroup: /user.slice/user-1001.slice/user@1001.service/app.slice/train_switch.service
             └─8522 /usr/bin/python3 app.py

Jan 15 20:55:46 raspberrypi systemd[644]: Started Train Switch.
Jan 15 20:55:50 raspberrypi python3[8522]:  * Serving Flask app "app" (lazy loading)
Jan 15 20:55:50 raspberrypi python3[8522]:  * Environment: production
Jan 15 20:55:50 raspberrypi python3[8522]:    WARNING: This is a development server. Do not use it in a production deployment.
Jan 15 20:55:50 raspberrypi python3[8522]:    Use a production WSGI server instead.
Jan 15 20:55:50 raspberrypi python3[8522]:  * Debug mode: off
```

If this fails due to a `User Service`, then ensure this line,
```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
```
is found in the `~/.bashrc` file followed by a system reboot, `sudo reboot`. This error is commonly caused when developing from a `ssh` connection.

## Viewing the Web Server
- First, ensure the `RPi` and client machine (laptop, cellphone tablet, etc.) are on the same `WiFi` network. 
- On your client machine  browse to [`http://raspberrypi.local:5000`](http://raspberrypi.local:5000). If you have a custom `hostname`, replace  `rasberrypi` with your custom `hostname`.
- Alternatively, on the `RPi` you can run,
```bash
ifconfig wlan0
```
You should see something like this (likely with a different `inet` value),
```
wlan0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.0.0.204  netmask 255.255.255.0  broadcast 10.0.0.255
        ...
```
Browsing to the `inet` field with [`http://10.0.0.204:5000`](http://10.0.0.204:5000) will also allow you to view the web server.
