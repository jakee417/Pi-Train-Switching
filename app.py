"""Web server for train switches"""
from flask import Flask, render_template, request

from python.utils import (
	setup_logging, read_logs, check_working_directory, PICKLE_PATH, PINOUT,
	GPIO_PINS, sort_pool, save_cfg, load_cfg, close_devices, update_pin_pool,
	construct_from_cfg
)
from python.train_switch import CLS_MAP

check_working_directory()
app = Flask(__name__)
setup_logging()

# container for holding our switches - load or set defaults
cfg, _ = load_cfg(PICKLE_PATH)
if cfg:
	devices = construct_from_cfg(cfg, app.logger)
	pin_pool = update_pin_pool(devices)
else:
	devices = {}

	# Now add one servo and one relay switch as default
	devices.update({
		str(pin): CLS_MAP['servo']( pin=pin, logger=app.logger) 
		for _, pin in enumerate([7])
	})
	devices.update({
		str(pins): CLS_MAP['relay'](pin=pins, logger=app.logger)
		for _, pins in enumerate([(3, 5)])
	})
	pin_pool = GPIO_PINS.copy() - set([3, 5, 7])

@app.route('/', methods = ['POST', 'GET'])
def index():
	if request.method == 'POST':
		for pin, action in request.form.items():
			devices[pin].action(action)  # perform action
	return render_template('index.html', devices=devices)

@app.route('/log/', methods = ['GET'])
def log():
	return render_template('log.html', log=read_logs())

@app.route('/about/', methods = ['GET'])
def about():
	return render_template('about.html')

@app.route('/beast/', methods = ['GET'])
def beast():
	return render_template('beast.html')

@app.route('/save/', methods = ['GET'])
def save():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved switches: {devices}')
	return render_template(
		'config.html', 
		devices=devices, 
		message=message,
		pin_pool=sort_pool(pin_pool), 
		pinout=PINOUT
	)

@app.route('/load/', methods = ['GET'])
def load():
	global devices
	global pin_pool
	try:
		cfg, message = load_cfg(PICKLE_PATH)
		if not cfg:
			return render_template(
				'config.html',
				devices=devices,
				message=message,
				pin_pool=sort_pool(pin_pool),
				pinout=PINOUT
			) 
		close_devices(devices)  # close out old devices
		devices = construct_from_cfg(cfg, app.logger)  # start new devices
		app.logger.info(f'++++ loaded switches: {devices}')
		pin_pool = update_pin_pool(devices)
	except Exception as e:
		message = e
	return render_template(
		'config.html',
		devices=devices,
		message=message,
		pin_pool=sort_pool(pin_pool),
		pinout=PINOUT
	)

@app.route('/config/', methods = ['GET', 'POST'])
def config():
	error = None
	if request.method == 'POST':
		########################################################################
		# remove pin logic
		########################################################################
		for pin, action in request.form.items():
			if pin in devices and action == 'delete':
				deleted = devices.pop(pin)
				deleted.close()  # close out any used pins

				# add the pins back into the pool
				[pin_pool.add(p) for p in deleted.pin_list]
				app.logger.info(f'++++ {action} switch {deleted}...')
				return render_template(
					'config.html',
					devices=devices,
					pin_pool=sort_pool(pin_pool),
					pinout=PINOUT
				)
		########################################################################
		# add pin logic
		########################################################################
		if ('pin1' in request.form
			and 'pin2' in request.form 
			and 'type' in request.form):
			# parse switch type entry
			switch_type = request.form.get('type', None)
			if switch_type not in list(CLS_MAP.keys()):
				error = f"{switch_type} is not a valid device type."
				return render_template(
					'config.html', 
					devices=devices, 
					error=error,
					pin_pool=sort_pool(pin_pool),
					pinout=PINOUT
					)

			# parse pin entries
			pin1 = request.form.get('pin1', None)
			pin2 = request.form.get('pin2', None)

			if pin1:
				try:
					pin1 = int(pin1)
				except Exception as e:
					error = f"while parsing pin 1, {e}."
					return render_template(
						'config.html', 
						devices=devices, 
						error=error, 
						pin_pool=sort_pool(pin_pool),
						pinout=PINOUT
					)

			if pin2:
				try:
					pin2 = int(pin2)
				except Exception as e:
					error = f"while parsing pin 2, {e}."
					return render_template(
						'config.html', 
						devices=devices, 
						error=error,
						pin_pool=sort_pool(pin_pool),
						pinout=PINOUT
					)

			if pin1 == pin2:
				error = f"pins cannot be the same. Found {pin1} and {pin2}"
				return render_template(
					'config.html', 
					devices=devices, 
					error=error,
					pin_pool=sort_pool(pin_pool),
					pinout=PINOUT
				)

			# servo only needs one pin, relay two pins
			pins = pin1 if switch_type == 'servo' else (pin1, pin2)

			# ensure all pins are available for use
			if isinstance(pins, int):
				pin_list = [pins]
			else:
				pin_list = list(pins)
			for p in pin_list:
				if p not in pin_pool:
					error = f": pin {p} is not available."
					return render_template(
							'config.html', 
							devices=devices, 
							error=error,
							pin_pool=sort_pool(pin_pool),
							pinout=PINOUT
						)
			try:
				added = CLS_MAP.get(switch_type)(pin=pins, logger=app.logger)
			except Exception as e:
				error = f"while trying to construct a switch, {e}."
				return render_template(
					'config.html', 
					devices=devices, 
					error=error, 
					pin_pool=sort_pool(pin_pool),
					pinout=PINOUT
				)
			devices.update({str(pins): added})  # add to global container
			[pin_pool.remove(p) for p in added.pin_list]  # add used pins
	return render_template(
		'config.html',
		devices=devices, 
		error = error,
		pin_pool=sort_pool(pin_pool),
		pinout=PINOUT
		)

if __name__ == '__main__':
	# Run the app on 0.0.0.0 which is visible on the local network
	# if running avahi-daemon, we can access this with raspberrypi.local:5000
	# alternatively, we can set the host to the ipv4 address found with ifconfig
	app.run(host='0.0.0.0', port=5000)
	close_devices(devices)
