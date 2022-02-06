"""Web server for raspberry pi devices."""
# Reference: http://mattrichardson.com/Raspberry-Pi-Flask/index.html
import time
import os
from os import strerror
from flask import Flask, render_template, request
from flask.views import MethodView
from collections import OrderedDict

from python.utils import (
	setup_logging, read_logs, check_working_directory, PICKLE_PATH,
	GPIO_PINS, sort_pool, save_cfg, load_cfg, close_devices, update_pin_pool,
	construct_from_cfg, custom_pinout, api_return_dict, convert_csv_tuples
)
from python.train_switch import CLS_MAP
from python.lionchief import LionChief
# from python.bluetooth import show_all_devices


########################################################################
# Setup
########################################################################
check_working_directory()
app = Flask(__name__)
setup_logging()

# setup ble devices
ble_devices = {}

# container for holding our devices - load or initialize
cfg, _ = load_cfg(PICKLE_PATH)
if cfg:
	devices = construct_from_cfg(cfg, app.logger)
	pin_pool = update_pin_pool(devices)
else:
	devices = OrderedDict({})
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
	return render_template(
		'log.html', 
		log=f"\n {read_logs()}",
		# ble_log=f"\n {show_all_devices()}"
	)

# @app.route('/about/')
# def about():
# 	return render_template('about.html')

# For latency testing purposes
# @app.route('/beast/')
# def beast():
# 	return render_template('beast.html')

@app.route('/save/')
def save():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved devices: {devices}')
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
		app.logger.info(f'++++ loaded devices: {devices}')
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

@app.route('/pinout/')
def pinout():
	global pin_pool
	return render_template(
		'pinout.html',
		pinout=custom_pinout(pin_pool)
	)

@app.route('/config/load', methods = ['POST'])
def config_load():
	global devices
	global pin_pool
	error = None

	# parse entries
	device_type = request.form.get('type', None)
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
		added = CLS_MAP.get(device_type)(pin=pins, logger=app.logger)
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

@app.route('/config/shuffle/<string:pins>/<string:direction>', methods=['POST',])
def config_shuffle(pins: str, direction: str):
	global devices
	pins = str(convert_csv_tuples(pins))
	curr_index = [i for i, (k, v) in enumerate(devices.items()) if k == pins]
	assert len(curr_index) == 1
	curr_index = curr_index[0]
	current_order = list(devices.keys())
	app.logger.info(f"++++ Current Order: {current_order}")
	app.logger.info(f"++++ Swapping pin: {pins} @ index: {curr_index}")
	if direction == 'up' and curr_index != 0:
		swapped = current_order[curr_index - 1]
		current_order[curr_index - 1] = pins
		current_order[curr_index] = swapped
	elif direction == 'down' and curr_index + 1 != len(current_order):
		swapped = current_order[curr_index + 1]
		current_order[curr_index + 1] = pins
		current_order[curr_index] = swapped
	app.logger.info(f"++++ New Order: {current_order}")
	devices = OrderedDict((k, devices[k]) for k in current_order)
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
			return api_return_dict(devices)
		else:
			pins = convert_csv_tuples(pins)
			return_devices = devices.get(str(pins), {})
			return api_return_dict({pins: return_devices})

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

		return api_return_dict(devices)

	def delete(self, pins: str) -> dict:
		"""Deletes a device."""
		pins = convert_csv_tuples(pins)
		deleted = devices.pop(str(pins), None)
		if deleted:
			deleted.close()

			# add the pins back into the pool
			[pin_pool.add(p) for p in deleted.pin_list]

		return api_return_dict(devices)

	def put(self, pins: str, action: str) -> dict:
		"""Updates the state of a device."""
		pins = convert_csv_tuples(pins)
		devices[str(pins)].action(action.lower())
		return api_return_dict(devices)

device_view = DevicesAPI.as_view('devices_api')
app.add_url_rule('/devices/', defaults={'pins': None}, view_func=device_view, methods=['GET',])
app.add_url_rule('/devices/<string:pins>', view_func=device_view, methods=['GET', 'DELETE'])
app.add_url_rule('/devices/<string:pins>/<string:device_type>', view_func=device_view, methods=['POST',])
app.add_url_rule('/devices/<string:pins>/<string:action>', view_func=device_view, methods=['PUT',])

@app.route('/devices/save', methods=['POST',])
def save_json():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved devices: {devices}')
	return api_return_dict(devices)

@app.route('/devices/load', methods=['POST',])
def load_json():
	global devices
	global pin_pool
	cfg, message = load_cfg(PICKLE_PATH)
	if cfg:
		close_devices(devices)  # close out old devices
		devices = construct_from_cfg(cfg, app.logger)  # start new devices
		app.logger.info(f'++++ loaded devices: {devices}')
		pin_pool = update_pin_pool(devices)
	return api_return_dict(devices)

@app.route('/train/start')
def start_train():
	global ble_devices
	if 'chief' not in ble_devices:
		# init one time
		ble_devices['chief'] = LionChief(
			"34:14:B5:3E:A4:71",
			app.logger
		)
		app.logger.info("++++ chief created")

	try:
		ble_devices['chief'].connect()
		time.sleep(0.25)
		app.logger.info(f"++++ chief connected: {ble_devices['chief'].connected}")
	except Exception as e:
		app.logger.error(e)

	if ble_devices['chief'].connected:
		ble_devices['chief'].ramp(9)
		ble_devices['chief'].horn_seq(' .  . ')
		ble_devices['chief'].speak(1)
	return {'connected': ble_devices['chief'].connected}

@app.route('/train/stop')
def stop_train():
	global ble_devices
	if 'chief' in ble_devices:
		if ble_devices['chief'].connected:
			app.logger.info("++++ unconnecting train...")
			ble_devices['chief'].ramp(0)
			ble_devices['chief'].close()
		return {'connected': ble_devices['chief'].connected}
	return {'connected': False}


if __name__ == '__main__':
	# Run the app on 0.0.0.0 which is visible on the local network
	# if running avahi-daemon, we can access this with raspberrypi.local:5000
	# alternatively, we can set the host to the ipv4 address found with ifconfig
	app.run(host='0.0.0.0', port=5000)
	close_devices(devices)
