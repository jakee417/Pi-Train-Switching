"""Web server for train switches"""
# Reference: http://mattrichardson.com/Raspberry-Pi-Flask/index.html

from os import strerror
from flask import Flask, render_template, request
from flask.views import MethodView

from python.utils import (
	setup_logging, read_logs, check_working_directory, PICKLE_PATH,
	GPIO_PINS, sort_pool, save_cfg, load_cfg, close_devices, update_pin_pool,
	construct_from_cfg, custom_pinout, devices_to_json, convert_csv_tuples
)
from python.train_switch import CLS_MAP


########################################################################
# Setup
########################################################################
check_working_directory()
app = Flask(__name__)
setup_logging()

# container for holding our switches - load or initialize
cfg, _ = load_cfg(PICKLE_PATH)
if cfg:
	devices = construct_from_cfg(cfg, app.logger)
	pin_pool = update_pin_pool(devices)
else:
	devices = {}
	pin_pool = GPIO_PINS.copy()


########################################################################
# HTML return methods
########################################################################
@app.route('/', methods = ['GET', 'POST'])
def index():
	global devices
	if request.method == 'POST':
		for pin, action in request.form.items():
			devices[pin].action(action.lower())  # perform action
	return render_template('index.html', devices=devices)

@app.route('/log/')
def log():
	return render_template('log.html', log=read_logs())

@app.route('/about/')
def about():
	return render_template('about.html')

# For latency testing purposes
# @app.route('/beast/')
# def beast():
# 	return render_template('beast.html')

@app.route('/save/')
def save():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved switches: {devices}')
	return render_template(
		'config.html', 
		devices=devices, 
		message=message,
		pin_pool=sort_pool(pin_pool), 
		pinout=custom_pinout(pin_pool)
	)

@app.route('/load/')
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
				pinout=custom_pinout(pin_pool)
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
		pinout=custom_pinout(pin_pool)
	)

@app.route('/config/')
def config():
	global devices
	global pin_pool
	return render_template(
		'config.html',
		devices=devices,
		pin_pool=sort_pool(pin_pool),
		pinout=custom_pinout(pin_pool)
		)

@app.route('/config/load', methods = ['POST'])
def config_load():
	global devices
	global pin_pool
	error = None

	# parse entries
	switch_type = request.form.get('type', None)
	pins = [
		int(v) for k, v in request.form.items()
		if k.startswith('pin') and v
	 ]

	# ensure pins are available
	for p in pins:
		if p not in pin_pool:
			error = f": pin {p} is not available."
			return render_template(
					'config.html',
					devices=devices,
					error=error,
					pin_pool=sort_pool(pin_pool),
					pinout=custom_pinout(pin_pool)
				)

	# cannot have duplicate pins
	if len(set(pins)) != len(pins):
		error = f"pins cannot be the same. Found: {pins}"
		return render_template(
			'config.html',
			devices=devices,
			error=error,
			pin_pool=sort_pool(pin_pool),
			pinout=custom_pinout(pin_pool)
		)

	# unpack if necessary
	pins = pins[0] if len(pins) == 1 else tuple(pins)

	# Attempt device construction
	try:
		added = CLS_MAP.get(switch_type)(pin=pins, logger=app.logger)
	except Exception as e:
		error = f"while trying to construct the device."
		return render_template(
			'config.html',
			devices=devices,
			error=error,
			pin_pool=sort_pool(pin_pool),
			pinout=custom_pinout(pin_pool)
		)
	devices.update({str(added.pin): added})  # add to global container
	[pin_pool.remove(p) for p in added.pin_list]  # add used pins
	return render_template(
		'config.html',
		devices=devices,
		error = error,
		pin_pool=sort_pool(pin_pool),
		pinout=custom_pinout(pin_pool)
	)

@app.route('/config/delete/<string:pins>', methods = ['POST',])
def config_delete(pins: str):
	global devices
	global pin_pool
	pins = convert_csv_tuples(pins)
	deleted = devices.pop(str(pins), None)
	if deleted:
		deleted.close()  # close out any used pins

		# add the pins back into the pool
		[pin_pool.add(p) for p in deleted.pin_list]
	return render_template(
		'config.html',
		devices=devices,
		pin_pool=sort_pool(pin_pool),
		pinout=custom_pinout(pin_pool)
	)

########################################################################
# RESTful API (JSON return types)
########################################################################

class DevicesAPI(MethodView):

	def get(self, pins: str) -> dict:
		"""Gets information about many devices, or one device."""
		if pins is None:
			return devices_to_json(devices)
		else:
			pins = convert_csv_tuples(pins)
			return devices_to_json({pins: devices[str(pins)]})

	def post(self, pins: str, device_type: str) -> dict:
		"""Adds a new device."""
		device_type = CLS_MAP.get(device_type, None)

		# device type must be legal
		if device_type:
			pins = convert_csv_tuples(pins)

			# pins must be available and not the same
			if all([p in pin_pool for p in pins]) and len(set(pins))==len(pins):
				added = device_type(pin=pins, logger=app.logger)
				devices.update({str(pins): added})  # add to global container
				[pin_pool.remove(p) for p in added.pin_list]  # remove availability

		return devices_to_json(devices)

	def delete(self, pins: str) -> dict:
		"""Deletes a device."""
		pins = convert_csv_tuples(pins)
		deleted = devices.pop(str(pins), None)
		if deleted:
			deleted.close()

			# add the pins back into the pool
			[pin_pool.add(p) for p in deleted.pin_list]

		return devices_to_json(devices)

	def put(self, pins: str, action: str) -> dict:
		"""Updates the state of a device."""
		pins = convert_csv_tuples(pins)
		devices[str(pins)].action(action.lower())
		return devices_to_json(devices)

device_view = DevicesAPI.as_view('devices_api')
app.add_url_rule('/devices/', defaults={'pins': None}, view_func=device_view, methods=['GET',])
app.add_url_rule('/devices/<string:pins>', view_func=device_view, methods=['GET', 'DELETE'])
app.add_url_rule('/devices/<string:pins>/<string:device_type>', view_func=device_view, methods=['POST',])
app.add_url_rule('/devices/<string:pins>/<string:action>', view_func=device_view, methods=['PUT',])

@app.route('/devices/save', methods=['POST',])
def save_json():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved switches: {devices}')
	return devices_to_json(devices)

@app.route('/devices/load', methods=['POST',])
def load_json():
	global devices
	global pin_pool
	cfg, message = load_cfg(PICKLE_PATH)
	if cfg:
		close_devices(devices)  # close out old devices
		devices = construct_from_cfg(cfg, app.logger)  # start new devices
		app.logger.info(f'++++ loaded switches: {devices}')
		pin_pool = update_pin_pool(devices)
	return devices_to_json(devices)


if __name__ == '__main__':
	# Run the app on 0.0.0.0 which is visible on the local network
	# if running avahi-daemon, we can access this with raspberrypi.local:5000
	# alternatively, we can set the host to the ipv4 address found with ifconfig
	app.run(host='0.0.0.0', port=5000)
	close_devices(devices)
