"""Web server for train switches"""
from flask import Flask, render_template, request

from python.utils import setup_logging, read_logs, check_working_directory
from python.train_switch import ServoTrainSwitch, RelayTrainSwitch

check_working_directory()
app = Flask(__name__)
setup_logging()

# TODO: Add these switches on a config page as well
train_switches = {
	'servo_' + str(switch): ServoTrainSwitch(switch='servo_' + str(switch), pin=pin, logger=app.logger) 
	for switch, pin in enumerate([7, 11, 13, 15])
}

other = {
	'relay_' + str(switch): RelayTrainSwitch(switch='relay_' + str(switch), pin=pins, logger=app.logger)
	for switch, pins in enumerate([(16, 18), (29, 31), (33, 37), (22, 32), (3, 5), (8, 10)])
}

train_switches.update(other)

@app.route('/', methods = ['POST', 'GET'])
def index():
	if request.method == 'POST':
		for switch, action in request.form.items():
			switch = switch  # cast the switch to an integer
			train_switches[switch].action(action)  # perform action
	return render_template('index.html', train_switches=train_switches)

@app.route('/log/', methods = ['GET'])
def log():
	return render_template('log.html', log=read_logs())
 
if __name__ == '__main__':
	# Run the app on 0.0.0.0 which is visible on the local network
	# if running avahi-daemon, we can access this with raspberrypi.local:5000
	# alternatively, we can set the host to the ipv4 address found with ifconfig
	app.run(host='0.0.0.0', port=5000)

	# close connections
	for _, train_switch in train_switches.items():
		train_switch.close()
