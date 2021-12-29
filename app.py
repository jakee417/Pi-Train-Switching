from flask import Flask, render_template, request
from train_switch.train_switch import TrainSwitch

NUM_SWITCHES = 2

pins = [7, 11, 12, 13, 15, 16, 18, 22]

train_switches = {
	i: TrainSwitch(switch=i, pin=pins[i], verbose=True) 
	for i in range(NUM_SWITCHES)
}

app = Flask(__name__)

@app.route('/', methods = ['POST', 'GET'])
def index():
	if request.method == 'POST':
		for switch, action in request.form.items():
			switch = int(switch)  # cast the switch to an integer
			train_switches[switch].action(action)
	return render_template('index.html')
 
if __name__ == '__main__':
	app.run(host = '192.168.1.220')
