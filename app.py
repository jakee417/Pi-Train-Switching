"""Web server for raspberry pi devices."""
# Reference: http://mattrichardson.com/Raspberry-Pi-Flask/index.html
from flask import Flask, render_template, request, jsonify, request
from flask.views import MethodView

from collections import OrderedDict
import os

from python.utils import (
	setup_logging, read_logs, check_working_directory, PICKLE_PATH, DEFAULT_PATH,
	GPIO_PINS, sort_pool, save_cfg, load_cfg, close_devices, update_pin_pool,
	construct_from_cfg, custom_pinout, api_return_dict, convert_csv_tuples,
        ios_return_dict, remove_cfg
)
from python.train_switch import CLS_MAP


########################################################################
# Setup
########################################################################
check_working_directory()
app = Flask(__name__)
setup_logging()

# container for holding our devices - load or initialize
devices = OrderedDict({})
pin_pool = GPIO_PINS.copy()

########################################################################
# HTML return methods
# These methods are largely deprecated and have been
# future proofed against newer versions of the app.
########################################################################
# FUTURE-PROOF
@app.route("/ip/", methods=["GET"])
def ip():
    return render_template(
		'ip.html',
		host_ip=request.host.split(':')[0],
		client_ip=request.remote_addr,
		host_port=request.host.split(':')[1]
	)

# FUTURE-PROOF
@app.route("/ip/json/", methods=["GET"])
def ip_json():
    return (
		jsonify(
			{
				"client_ip": request.remote_addr,
				"host_ip": request.host.split(':')[0],
				"host_port": request.host.split(':')[1]
			}
		),
		200
	)

# FUTURE-PROOF
@app.route('/', methods = ['GET', 'POST'])
def index():
	global devices
	if request.method == 'POST':
        # DEPRECATED
		for pin, action in request.form.items():
			devices[pin].action(action.lower())  # perform action
	return render_template('index_future.html', devices=devices)

# FUTURE-PROOF
@app.route('/log/')
def log():
	return render_template(
		'log.html',
		log=f"\n {read_logs()}",
	)

# DEPRECATED
@app.route('/save/')
def save():
	global devices
	message = save_cfg(devices)
	app.logger.info(f'++++ saved devices: {devices}')
	return render_template(
		'config.html', 
		devices=devices, 
		message=message,
		pin_pool=sort_pool(pin_pool)
	)

# DEPRECATED
@app.route('/load/')
def load():
	global devices
	global pin_pool
	try:
		cfg, message = load_cfg(DEFAULT_PATH)
		if not cfg:
			return render_template(
				'config.html',
				devices=devices,
				message=message,
				pin_pool=sort_pool(pin_pool)
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
		pin_pool=sort_pool(pin_pool)
	)

# DEPRECATED
@app.route('/config/')
def config():
	global devices
	global pin_pool
	return render_template(
		'config.html',
		devices=devices,
		pin_pool=sort_pool(pin_pool)
		)

# FUTURE-PROOF
@app.route('/pinout/')
def pinout():
	global pin_pool
	return render_template(
		'pinout_future.html',
		pinout=custom_pinout(pin_pool)
	)

# DEPRECATED
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
					pin_pool=sort_pool(pin_pool)
				)

	# cannot have duplicate pins
	if len(set(pins)) != len(pins):
		error = f"pins cannot be the same. Found: {pins}"
		return render_template(
			'config.html',
			devices=devices,
			error=error,
			pin_pool=sort_pool(pin_pool)
		)

	# Attempt device construction
	try:
		added = CLS_MAP.get(device_type)(pin=pins, logger=app.logger)
	except Exception as e:
		error = f"while trying to construct the device."
		return render_template(
			'config.html',
			devices=devices,
			error=error,
			pin_pool=sort_pool(pin_pool)
		)
	devices.update({str(added.pin): added})  # add to global container
	[pin_pool.remove(p) for p in added.pin_list]  # add used pins
	return render_template(
		'config.html',
		devices=devices,
		error = error,
		pin_pool=sort_pool(pin_pool)
	)

# DEPRECATED
@app.route('/config/delete/<string:pins>', methods = ['POST',])
def config_delete(pins: str):
	global devices
	global pin_pool
	pins = convert_csv_tuples(pins)
	deleted = devices.pop(str(pins), None)
	if deleted:
		deleted.close()  # close out any used pins
		[pin_pool.add(p) for p in deleted.pin_list]  # add back to pool
	return render_template(
		'config.html',
		devices=devices,
		pin_pool=sort_pool(pin_pool)
	)

# DEPRECATED
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
		pin_pool=sort_pool(pin_pool)
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


########################################################################
# iOS API (JSON return types)
# Backend to "Rail Yard" iOS app
########################################################################
DEVICE_TYPES = {
	k: {
		"requirement": v.required_pins
	}
	for k, v in CLS_MAP.items()
}

DEVICE_TYPES = list(CLS_MAP.keys())

@app.route('/devices/get')
def get() -> dict:
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/save/<string:name>')
def save_json(name: str) -> dict:
	global devices
	path = os.path.join(PICKLE_PATH, name.strip() + '.pkl')
	message = save_cfg(devices, path)
	app.logger.info(f'++++ saved devices: {devices} as {path}')
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/load/<string:name>')
def load_json(name: str) -> dict:
	global devices
	global pin_pool
	path = os.path.join(PICKLE_PATH, name + '.pkl')
	cfg, message = load_cfg(path)
	if cfg:
		close_devices(devices)  # close out old devices
		devices = construct_from_cfg(cfg, app.logger)  # start new devices
		app.logger.info(f'++++ loaded devices: {devices}')
		pin_pool = update_pin_pool(devices)
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/remove/<string:name>')
def remove_json(name: str) -> dict:
	path = os.path.join(PICKLE_PATH, name + '.pkl')
	message = remove_cfg(path)
	app.logger.info(f'++++ {message}')
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/toggle/<int:device>')
def toggle_index(device: int) -> dict:
	"""Toggle the state of a device, or set to 'self.on_state' by default."""
	global devices
	device -= 1  # user will see devices as 1-indexed, convert to 0-indexed
	order = [k for k, v in devices.items()]  # get ordering of pins
	pins = order[device]
	on_state = devices[str(pins)].on_state
	off_state = devices[str(pins)].off_state
	if devices[pins].state == on_state:
		devices[str(pins)].action(off_state)
	else:
		devices[str(pins)].action(on_state)
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/reset/<int:device>')
def reset_index(device: int) -> dict:
	"""Resets the state of a device."""
	global devices
	device -= 1  # user will see devices as 1-indexed, convert to 0-indexed
	order = [k for k, v in devices.items()]  # get ordering of pins
	pins = order[device]
	devices[pins].state = None
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)


@app.route('/devices/toggle/pins/<string:pins>')
def toggle_pins(pins: str) -> dict:
	"""Toggle the state of a device, or set to 'self.on_state' by default."""
	global devices
	pins = convert_csv_tuples(pins)
	on_state = devices[str(pins)].on_state
	off_state = devices[str(pins)].off_state
	if devices[pins].state == on_state:
		devices[str(pins)].action(off_state)
	else:
		devices[str(pins)].action(on_state)
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/delete/<string:pins>')
def delete(pins: str) -> dict:
	"""Deletes a device."""
	pins = convert_csv_tuples(pins)
	deleted = devices.pop(str(pins), None)
	if deleted:
		deleted.close()
		# add the pins back into the pool
		[pin_pool.add(p) for p in deleted.pin_list]
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)

@app.route('/devices/post/<string:pins>/<string:device_type>')
def post(pins: str, device_type: str) -> dict:
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
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)


@app.route('/devices/shuffle/<int:start>/<int:finish>')
def devices_shuffle(start: int, finish: int):
	global devices
	assert start >= 0 and start < len(devices) and finish >= 0 and finish <= len(devices)
	if finish != 0 and finish != len(devices) and start < finish:
		finish -= 1
	curr_index = [i for i, (k, v) in enumerate(devices.items())]
	current_order = list(devices.keys())
	app.logger.info(f"++++ Current Order: {current_order}")
	current_order.insert(finish, current_order.pop(start))
	app.logger.info(f"++++ New Order: {current_order}")
	devices = OrderedDict((k, devices[k]) for k in current_order)
	return ios_return_dict(devices, sort_pool(pin_pool), DEVICE_TYPES)


if __name__ == '__main__':
	# Run the app on 0.0.0.0 which is visible on the local network
	# if running avahi-daemon, we can access this with raspberrypi.local:5000
	# alternatively, we can set the host to the ipv4 address found with ifconfig
	app.run(host='0.0.0.0', port=5000)
	close_devices(devices)
