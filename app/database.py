import time
from datetime import datetime
import pytz
import numpy as np
from pymongo import MongoClient
from .utils import pre_normalization
import threading
from confluent_kafka import Consumer, KafkaException

class MongoDBHandler:

    def __init__(self, uri=None, db_name=None):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]  # db name

    def get_collection(self, collection_name):
        return self.db[collection_name]

    def insert(self, collection_name, data):
        collection = self.get_collection(collection_name)
        return collection.insert_one(data)

    def notify_training(self, message, collection_name="notification", local_timestamp=None):
        if not local_timestamp:
            # Local Timestamp
            la_timezone = pytz.timezone('America/Los_Angeles')
            local_timestamp = datetime.now(la_timezone).strftime('%Y-%m-%d %H:%M:%S')  # Readable local timestamp
        # UTC Timestamp
        timestamp = int(time.time() * 1000)  # UTC timestamp in milliseconds
        insert_data = {
            "message": message,
            "local_time": local_timestamp,
            "timestamp": timestamp
        }
        self.db.insert(collection_name, insert_data)

    def store_training_logs(self, logs, collection_name="training_logs", local_timestamp=None):
        if not local_timestamp:
            # Local Timestamp
            la_timezone = pytz.timezone('America/Los_Angeles')
            local_timestamp = datetime.now(la_timezone).strftime('%Y-%m-%d %H:%M:%S')  # Readable local timestamp
        # UTC Timestamp
        timestamp = int(time.time() * 1000)  # UTC timestamp in milliseconds
        insert_data = {
            "logs": logs,
            "local_time": local_timestamp,
            "service": "Training Service",
            "timestamp": timestamp
        }
        self.db.insert(collection_name, insert_data)

    # Example usage: log_training_status({"version": "1.0.0", "timestamp": "2023-11-13", "logs": logs})

    def fetch_poses(self,
                    collection_name="results",
                    num_of_poses=30,
                    past_time=None,
                    timestamp=None,
                    custom_shape=(3, 25)):
        collection = self.get_collection(collection_name)

        all_poses = []

        if past_time:
            # Calculate the time range
            start_time = timestamp - (past_time * 1000)

            query = {
                "timestamp": {"$gte": start_time, "$lte": timestamp},
                "service": "pose_detector",
                "pose": {"$ne": None}
            }

            # Fetch all poses within the time range
            results = list(collection.find(query).sort("timestamp", 1))

            if results:
                # Evenly distribute the selection of poses over the time range
                total_results = len(results)
                step = max(total_results // num_of_poses, 1)

                selected_indices = [i * step for i in range(num_of_poses) if i * step < total_results]

                for index in selected_indices:
                    pose_array = np.array(results[index]['pose'])
                    # print(results[index]["timestamp"])
                    if pose_array.shape[:-1] == custom_shape:
                        all_poses.append(pose_array)
                    else:
                        print(f"Unexpected shape for pose: {pose_array.shape}")

        else:
            # If past_time is not provided, fetch the latest poses
            query = {
                "timestamp": {"$lte": timestamp},
                "service": "pose_detector",
                "pose": {"$ne": None}
            }
            results = collection.find(query).limit(num_of_poses)
            for document in results:
                pose_array = np.array(document['pose'])
                if custom_shape and pose_array.shape[:-1] == custom_shape:
                    all_poses.append(pose_array)
                elif not custom_shape:
                    all_poses.append(pose_array)
                else:
                    print(f"Unexpected shape for document {document['_id']}: {pose_array.shape}")

        if len(all_poses) < num_of_poses:
            print(f"Only {len(all_poses)} poses found in the database. "
                  f"Please check if the pose detector is running properly.")
            return None

        all_poses_stacked = np.stack(all_poses, axis=0)

        # Reshape to ((shape), X) where X is flexible
        final_shape = (1, custom_shape[0], num_of_poses, custom_shape[1], -1)
        final_poses = all_poses_stacked.reshape(final_shape)

        training_poses = pre_normalization(final_poses)
        # print(training_poses.shape)
        return training_poses

    def store_labeled_pose(self, timestamp, poses, label, past_time=None, version=None,
                           collection_name="labeled_poses"):
        collection = self.get_collection(collection_name)
        # Assuming that poses is already a list of np.arrays with shape (3, 60, 25, 1)
        # Convert each np.array pose to a list before storing in MongoDB
        la_timezone = pytz.timezone('America/Los_Angeles')
        local_timestamp = datetime.now(la_timezone).strftime('%Y-%m-%d %H:%M:%S')  # Readable local timestamp

        print(poses.shape)
        pose_list = poses[0].tolist()  # Convert each (3, 60, 25, 1) pose to a list
        document = {
            "pose": pose_list,
            "label": label,
            "local_time": local_timestamp,
            "service": "Data Service 2",
            "timestamp": timestamp
        }
        if version is not None:
            document["version"] = version
        if past_time is not None:
            document["past_time"] = past_time

        collection.insert_one(document)


class KafkaMongoConsumer:
    def __init__(self, mongo_handler, kafka_config, topic, collection, batch_duration=1.0):
        self.mongo_handler = mongo_handler
        self.consumer = Consumer(kafka_config)
        self.topic = topic
        self.collection = collection
        self.running = False
        self.batch_duration = batch_duration

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def run(self):
        try:
            self.consumer.subscribe([self.topic])
            message_batch = []

            while self.running:
                msg = self.consumer.poll(0.1)  # Reduced poll timeout

                if msg is not None and not msg.error():
                    message_batch.append(msg.value())

                # Check if the batch duration has elapsed
                if len(message_batch) > 0 and time.time() - self.last_batch_time >= self.batch_duration:
                    # Insert the batch into MongoDB
                    self.mongo_handler.insert_many(self.collection, message_batch)
                    message_batch = []  # Reset the batch
                    self.last_batch_time = time.time()

        finally:
            self.consumer.close()


if __name__ == '__main__':
    # notify_training('Training started')
    # store_training_logs('Mock logging')
    mongodb = MongoDBHandler('mongodb://root:password@128.195.151.182:27017/', 'calit2')
    ts = 1700889359635
    duration = 5
    fetched_poses = mongodb.fetch_poses(timestamp=ts, past_time=duration)

    mongodb.store_labeled_pose(timestamp=ts, poses=fetched_poses, label=1, past_time=duration,
                               version="testing")
    # pose_array, label_list = mongodb.fetch_new_set(number=60)
    # print(pose_array.shape)
    # print(label_list)
    # label_1_aary, label_0_array, label_array = fetch_new_set_seperate(number=10, label_1_count=2, label_0_count=2)
    # print(label_1_aary.shape)
    # print(label_0_array.shape)
    # print(pose_aary.shape)
    # print(label_array)

    # store_labeled_pose (poses=poses, label=1, past_time=past_time, timestamp=ts, version="testing")
