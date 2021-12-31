from flask import Flask, render_template, request
from RPi import GPIO
from train_switch.train_switch import (
	ManualTrainSwitch, AngularServoTrainSwitch
)

NUM_SWITCHES = 2  # match number of button sets on html page

pins = [7, 11, 12, 13, 15, 16, 18, 22]

"""
for each pin# in all the possible pin #'s:
	make a train switch on this pin#
	stop if we reach the NUM_SWITCHES
"""
train_switches = {
	i: AngularServoTrainSwitch(switch=i, pin=pins[i], verbose=True) 
	for i in range(NUM_SWITCHES)
}

app = Flask(__name__)

@app.route('/', methods = ['POST', 'GET'])
def index():
	if request.method == 'POST':
		for switch, action in request.form.items():
			switch = int(switch)  # cast the switch to an integer
			train_switches[switch].action(action)
	# TODO: if its a post, we need to pass arguments to `index.html`
	return render_template('index.html')
 
if __name__ == '__main__':
	app.run(host = '192.168.1.220')

	# close connections
	for _, train_switch in train_switches.items():
		train_switch.close()
