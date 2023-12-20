from .save_trigger import PowerMeterReceiver
from flask import blueprints, request, jsonify
from app import mongodb

BASE_URL = "http://128.195.151.182:9001/api/data"
THRESHOLD = 15
STREAM_SEGMENTER_URL = "http://128.195.151.182:9095/api/v1/web_stream"
# TRAINER_URL = "http://128.195.151.170:30081"
SAVE_TIME = 3   # seconds
TRIGGER_TIME = 0.1  # minutes
CAMERA_NAME_LIST = ["pi-cam-3", "pi-cam-6"]
DEVICE_NAME = "power-meter-14"
# DEVICE_NAME = "mock-power-meter-1"
VALUE_KEY = "Current"

receiver = PowerMeterReceiver(base_url=BASE_URL, device_name=DEVICE_NAME, threshold=THRESHOLD, save_time=SAVE_TIME,
                              camera_base_url=STREAM_SEGMENTER_URL, camera_name_list=CAMERA_NAME_LIST, trigger_time=TRIGGER_TIME,
                              value_key=VALUE_KEY, mongo_db=mongodb, frequency=0)
print("Starting receiver...")
receiver.start()

print("Receiver started successfully")

trigger_blueprint = blueprints.Blueprint('tigger', __name__, url_prefix='/api/v1/trigger')


@trigger_blueprint.route('/update_info', methods=['POST'])
def update_info():

    data = request.json
    if 'camera_base_url' in data:
        receiver.camera_base_url = data['camera_base_url']
    if 'stream_url' in data:
        receiver.stream_url = data['stream_url']
    if 'camera_name' in data:
        receiver.camera_name_list = data['camera_name_list']
    if 'device_name' in data:
        receiver.device_name = data['device_name']
    if 'trainer_url' in data:
        receiver.trainer_url = data['trainer_url']
    if 'value_key' in data:
        receiver.value_key = data['value_key']
    if 'save_time' in data:
        receiver.save_time = data['save_time']
    if 'threshold' in data:
        receiver.threshold = data['threshold']
    if 'trigger_time' in data:
        receiver.auto_insert_time = data['trigger_time']

    if 'status' in data:
        status = data['labe']
        if status in [1, 0, -1]:
            receiver.change_status(status=status)
        else:
            return jsonify({"error": "Invalid status value"}), 400
    receiver.stop()
    receiver.start()
    return jsonify({"message": "Information updated successfully"}), 200


@trigger_blueprint.route('/get_info', methods=['GET'])
def get_info():
    info = {
        "camera_base_url": receiver.camera_base_url,
        "camera_name_list": receiver.camera_name_list,
        "stream_url": receiver.stream_url,
        "device_name": receiver.device_name,
        "has_pose": receiver.has_pose,
        "value_key": receiver.value_key,
        "save_time": receiver.save_time,
        "threshold": receiver.threshold,
        "trigger_time": receiver.auto_insert_time,
        "label_count": receiver.label_count,
        "status": receiver.check_status()
    }
    return jsonify(info), 200


@trigger_blueprint.route('/pose_status')
def pose_status():
    pose_detected = request.args.get('detected', 'false')
    # Convert the string to a boolean
    if pose_detected.lower() == 'true':
        pose_detected = True
    else:
        pose_detected = False

    receiver.has_pose = pose_detected
    # Return a response to the notifier
    return f"Detect pose {receiver.has_pose}", 200


@trigger_blueprint.route('/change_status/<string:status>', methods=['GET'])
def change_status(status):
    status = int(status)
    if status in [1, 0, -1]:
        status = receiver.change_status(status=status)
        return jsonify({"message": f"Change status to {status}"}), 200
    else:
        return jsonify({"error": "Invalid status value"}), 400


@trigger_blueprint.route('/check_status', methods=['GET'])
def check_status():
    status = receiver.check_status()
    return jsonify({"message": f"Current status is {status}"}), 200


@trigger_blueprint.route('/start', methods=['GET'])
def start():
    message = receiver.start()
    return jsonify({"message": message}), 200


@trigger_blueprint.route('/stop', methods=['GET'])
def stop():
    message = receiver.stop()
    return jsonify({"message": "Receiver stopped successfully"}), 200


@trigger_blueprint.route('/start_auto_labeling', methods=['POST'])
def start_labeling():
    receiver.start_auto_labeling()
    return jsonify({"message": "Labeling started successfully"}), 200


@trigger_blueprint.route('/stop_auto_labeling', methods=['POST'])
def stop_labeling():
    receiver.stop_auto_labeling()
    return jsonify({"message": "Labeling stopped successfully"}), 200
