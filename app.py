from flask import Flask, render_template, request
from train_switch.train_switch import GPIOZeroManualTrainSwitch, RelayTrainSwitch

NUM_SWITCHES = 2  # match number of button sets on html page

pins = [7, 11, 12, 13, 15, 16, 18, 22]  # board pins, 8 total

train_switches = {
	i: GPIOZeroManualTrainSwitch(switch=i, pin=pins[i], verbose=True) 
	for i in range(NUM_SWITCHES)
}

train_switches.update(
	{2: RelayTrainSwitch(switch=2, pin=(8, 10), verbose=True)}
)

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
	# app.run(host='0.0.0.0', port=80, debug=True)
	app.run(host='192.168.1.220')

	# close connections
	for _, train_switch in train_switches.items():
		train_switch.close()
