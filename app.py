from flask import Flask, render_template, request
from train_switch.train_switch import ServoTrainSwitch, RelayTrainSwitch

train_switches = {
	switch: ServoTrainSwitch(switch=switch, pin=pin, verbose=True) 
	for switch, pin in enumerate([7, 11])
}

train_switches.update(
	{2: RelayTrainSwitch(switch=2, pin=(16, 18), verbose=True)}
)

app = Flask(__name__)

@app.route('/', methods = ['POST', 'GET'])
def index():
	kwargs = {}
	if request.method == 'POST':
		for switch, action in request.form.items():
			switch = int(switch)  # cast the switch to an integer
			train_switches[switch].action(action)
	# TODO: if its a post, we need to pass arguments to `index.html`
	kwargs = {"name_" + str(i): s.__repr__() for i, s in train_switches.items()}
	kwargs.update({"status_" + str(i): str(s.state) for i, s in train_switches.items()})
	kwargs.update({'title': 'Train Switches'})
	return render_template('index.html', **kwargs)
 
if __name__ == '__main__':
	# app.run(host='0.0.0.0', port=80, debug=True)
	app.run(host='192.168.1.220')

	# close connections
	for _, train_switch in train_switches.items():
		train_switch.close()
