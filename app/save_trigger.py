import threading
from datetime import datetime, timedelta

import pytz

from .database import MongoDBHandler
import requests
import time
import json


class PowerMeterReceiver:

    def __init__(self, base_url, device_name, threshold, camera_base_url, camera_name, value_key, frequency=0,
                 save_time=5, trigger_time=5, mongo_db=None, status=0):
        # self.stream_url = f"{base_url}/kafka_stream/latest/{device_name}"
        self.label_count = {0: 0, 1: 0}
        self.stream_url = f"{base_url}/kafka_stream/{device_name}?frequency={frequency}"
        self.threshold = threshold
        self.device_name = device_name
        self.save_time = save_time  # for saving past video and poses
        self.auto_insert_time = trigger_time  # for triggering the label insertion
        self.status = status
        self.camera_base_url = camera_base_url
        self.camera_name = camera_name
        self.previous_value = None
        self.value_key = value_key
        self.mongo_db = mongo_db
        self.notification_db = 'notification'
        self.monitor_thread = None
        self.auto_tagging = True  # A flag to control the scheduling
        self.event_tagging = False
        self.monitor_flag = True
        # deprecated
        self.has_pose = True

    def schedule_labeling(self, interval_in_minutes=10):
        """Schedule a label to be inserted at regular intervals."""
        # Calculate the next trigger time
        next_trigger_time = datetime.now() + timedelta(minutes=interval_in_minutes)
        print(next_trigger_time)
        # Schedule the insert_label to be called
        threading.Timer(interval_in_minutes * 60, self.trigger_label_auto_insertion).start()

        print(f"Labeling scheduled at: {next_trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def trigger_label_auto_insertion(self):
        """Trigger label insertion and reschedule the next one."""
        if self.auto_tagging:
            label = self.status
            print(f"Time for auto label insertion... current label: {label}")
            if not self.event_tagging and self.has_pose:
                timestamp = int(time.time() * 1000)
                time.sleep(10)
                print("Inserting label...")
                self.insert_label(label=label, timestamp=timestamp)
            # Reschedule the next trigger
            self.schedule_labeling(interval_in_minutes=self.auto_insert_time)

    def start_auto_labeling(self):
        """Start the periodic labeling process."""
        self.auto_tagging = True
        self.schedule_labeling(interval_in_minutes=self.auto_insert_time)

    def stop_auto_labeling(self):
        """Stop the periodic labeling process."""
        self.auto_tagging = False

    def event_triggering_process(self, past_video=True, save_time=None, timestamp=None, label=None):

        if label is None:
            label = self.status
        self.save_event_triggered_notification(label=label, timestamp=timestamp, database=self.notification_db)
        print("saving video...")
        """Save past video segments and schedule to save future video segments."""
        if past_video:
            self._save_past_video(save_time, timestamp=timestamp)
        elif save_time is not None:
            self._save_next_video(save_time, timestamp=timestamp)
        time.sleep(10)
        # label = 1 in here
        print("inserting label...")
        self.insert_label(label=label, timestamp=timestamp)

    def _save_past_video(self, save_time=None, timestamp=None):
        """Save past video segments."""
        try:
            if timestamp:
                print("startime", timestamp - (save_time * 1000), "stoptime", timestamp)
                response = requests.post(f"{self.camera_base_url}/save_past",
                                         json={"camera_name": self.camera_name,
                                               "start_time": timestamp - (save_time * 1000),
                                               "stop_time": timestamp,
                                               "is_timestamps": True
                                               }
                                         )
            else:
                response = requests.post(f"{self.camera_base_url}/save_past",
                                         json={"camera_name": self.camera_name,
                                               "start_time": save_time,
                                               "stop_time": 0
                                               }
                                         )
            if response.status_code == 200:
                print(response.json().get('status', 'Operation completed'))
            else:
                print(f"Error saving past video: {response.text}")
        except requests.RequestException as e:
            print(f"Error saving past video: {e}")

    def _save_next_video(self, save_time=None, timestamp=None):
        """Schedule to save future video segments."""
        try:
            response = requests.post(f"{self.camera_base_url}/save_next",
                                     json={"camera_name": self.camera_name,
                                           "save_time": save_time
                                           }
                                     )
            if response.status_code == 200:
                print(response.json().get('status', 'Operation completed'))
            else:
                print(f"Error scheduling next video save: {response.text}")
        except requests.RequestException as e:
            print(f"Error scheduling next video save: {e}")

    def save_event_triggered_notification(self, label=0, database='notification', duration=None, timestamp=None):
        """Save status change."""
        try:
            if duration is None:
                duration = self.save_time
            self.mongo_db.insert(database,
                                 {'service': self.device_name, 'label_status': label, 'timestamp': timestamp,
                                  'duration': duration})
        except Exception as e:
            print(f"Error saving status change: {e}")

    def insert_label(self, label=None, max_retries=3, delay_between_retries=0, timestamp=None):
        """Tagging the poses with the label"""

        if not label:
            label = self.status
        if not timestamp:
            timestamp = int(time.time() * 1000)
        try:
            poses = self.mongo_db.fetch_poses(timestamp=timestamp, past_time=self.save_time)
            print("auto fetched complete")
            self.mongo_db.store_labeled_pose(timestamp=timestamp, poses=poses, label=label, past_time=self.save_time)
            self.label_count[self.status] += 1
        except Exception as e:
            print(f"Error inserting labeled poses: {e}")
        # retries = 0
        # data_to_send = {
        #     'timestamp': timestamp,
        #     # this seems more resonable and I would refact a more resonable mechanism later
        #     'label': label,
        #     # Assume 'past_time' and 'version' are handled elsewhere if needed
        #     'duration': self.save_time,
        # }
        # while retries < max_retries:
        #     try:
        #         response = requests.post(url=f"{self.trainer_url}/label_poses",
        #                                  json=data_to_send)
        #         if 200 <= response.status_code < 300:
        #             return
        #         else:
        #             print(f"Error inserting label for training: {response.status_code}")
        #     except Exception as e:
        #         print(f"Error saving status change: {e}")
        #
        #     retries += 1
        #     if retries < max_retries:
        #         print(f"Retrying registration in {delay_between_retries} seconds...")
        #         time.sleep(delay_between_retries)
        # print("Max retries reached, failed to insert label.")

    def process_data_point(self, data_point):
        """Process a single data point from the power meter stream."""
        # print("processing data points")
        current_value = data_point.get("values", {}).get(self.value_key)
        time_string = data_point.get("time")
        dt = datetime.strptime(time_string, "%m/%d/%Y %H:%M:%S.%f").replace(tzinfo=pytz.utc)

        # Convert the timezone-aware datetime object into a timestamp (in seconds)
        # print(current_value)
        # Convert to Unix timestamp in milliseconds
        timestamp = int(dt.timestamp() * 1000)
        if current_value is None:
            return

        if self.previous_value is not None and current_value - self.previous_value >= self.threshold:
            self.status = 1
            print("status changed", self.status, "previous value", self.previous_value, "current value", current_value)
            self.event_tagging = True

            threading.Thread(
                target=self.event_triggering_process,
                kwargs={
                    'past_video': True,
                    'save_time': self.save_time,
                    'timestamp': timestamp,
                    'label': self.status
                }
            ).start()

            threading.Timer(self.save_time, self.change_status, args=(0,)).start()  # Resets after 5 second
        else:
            self.previous_value = current_value

    def change_status(self, status=0):
        self.status = status
        if status == 0:
            self.event_tagging = False
        # elif status == 1:
        #     self.event_tagging = True
        return self.status

    def check_status(self):
        return self.status

    def start_monitoring(self):
        """Continuously monitor the power meter stream and process incoming data points."""
        while self.monitor_flag:
            try:
                with requests.get(self.stream_url, stream=True) as response:
                    # Ensure that the request was successful
                    response.raise_for_status()
                    print(self.stream_url)
                    print("stream received")
                    # Stream and process the data
                    for line in response.iter_lines():
                        if not self.monitor_flag:
                            break
                        if line:
                            # Parse the JSON data from the line
                            try:
                                decoded_line = line.decode('utf-8')
                                if decoded_line.startswith("data: "):
                                    # remove "data: " prefix and replace single quotes
                                    json_str = decoded_line[6:].replace("'", '"')
                                    data = json.loads(json_str)
                                    self.process_data_point(data)
                                else:
                                    print(f"Unexpected line format: {decoded_line}")
                            except json.JSONDecodeError:
                                print(f"Failed to decode JSON from line: {line.decode('utf-8')[6:]}")

            except requests.RequestException as e:
                print(f"Error while connecting to the power meter stream: {e}")
                time.sleep(10)
            print("starting another attempt in 10 seconds...")
            # try:
            #     print("there")
            #     response = requests.get(self.stream_url, stream=True)
            #     print("here")
            #     if response.status_code == 200:
            #         for line in response.iter_lines():
            #             if line:  # Check if the line is not empty
            #                 try:
            #                     # Check if the line starts with "data: " and strip it off
            #                     decoded_line = line.decode('utf-8')
            #                     if decoded_line.startswith("data: "):
            #                         json_str = decoded_line[6:].replace("'", '"')  # remove "data: " prefix and replace single quotes
            #                         data = json.loads(json_str)
            #                         self.process_data_point(data)
            #                     else:
            #                         print(f"Unexpected line format: {decoded_line}")
            #                 except json.JSONDecodeError:
            #                     print(f"Failed to decode JSON from line: {line.decode('utf-8')}")
            #     else:
            #         print(f"Failed to connect to power meter stream. Status code: {response.status_code}")
            #         time.sleep(10)
            #
            # except requests.RequestException as e:
            #     print(f"Error while connecting to the power meter stream: {e}")
            #     time.sleep(10)

    def start(self):
        if self.monitor_thread is not None:
            return "Already started"
        print("start the save_trigger")
        self.monitor_flag = True
        self.monitor_thread = threading.Thread(target=self.start_monitoring)
        self.monitor_thread.start()
        print("Starting labeling...")
        self.start_auto_labeling()
        return "Started"

    def stop(self):
        if self.monitor_thread is None:
            return "Already stopped"
        self.monitor_flag = False
        self.monitor_thread.join()
        self.stop_auto_labeling()
        self.monitor_thread = None
        return "Stopped"


if __name__ == "__main__":
    # Configuration
    BASE_URL = "http://128.195.151.182:9001/api/data"
    THRESHOLD = 10
    STREAM_SEGMENTER_URL = "http://128.195.151.182:9095/api/v1/web_stream/"
    CAMERA_NAME = "pi-cam-3"
    DEVICE_NAME = "power-meter-1"
    SAVE_TIME = 5  # seconds
    TRIGGER_TIME = 5  # minutes

    mongodb = MongoDBHandler('mongodb://root:password@128.195.151.182:27017/', 'calit2')

    VALUE_KEY = "Current"
    receiver = PowerMeterReceiver(base_url=BASE_URL, device_name=DEVICE_NAME, threshold=THRESHOLD, save_time=SAVE_TIME,
                                  camera_base_url=STREAM_SEGMENTER_URL, camera_name=CAMERA_NAME,
                                  trigger_time=TRIGGER_TIME, value_key=VALUE_KEY, mongo_db=mongodb, frequency=0)
    # receiver.event_triggering_process(past_video=True, save_time=5, timestamp=1700367756082, label=1)
    label = 1
    timestamp = 1700781155079
    receiver.save_event_triggered_notification(label=label, database='notification', timestamp=timestamp)
    receiver.insert_label(label=label, timestamp=timestamp)
