import time
from datetime import datetime
import pytz
import numpy as np
from pymongo import MongoClient
from .utils import pre_normalization


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

    def fetch_poses(self, collection_name="results", num_of_poses=10, past_time=None, timestamp=None):
        collection = self.get_collection(collection_name)
        
        if past_time:
            # Calculate the time range
            start_time = timestamp - (past_time * 1000)  # Convert past_time from seconds to milliseconds
            query = {
                "timestamp": {
                    "$gte": start_time,
                    "$lte": timestamp
                },
                "service": "pose_detector",
                "pose": {"$ne": None}  # Exclude documents where 'pose' is null
            }

            results = collection.find(query)

        else:
            # If past_time is not provided, fetch a specific number of documents (training_set + test_set)
            query = {
                "timestamp": {
                    "$lte": timestamp
                },
                "service": "pose_detector",
                "pose": {"$ne": None}  # Exclude documents where 'pose' is null
            }
            # Perform the query with a limit (uncomment the next line in your actual environment)
            results = collection.find(query).limit(num_of_poses)
            
        all_poses = []

        for document in results:
            # print(document)
            pose_arrays = np.array(document['pose'])
            if pose_arrays.shape == (3, 25, 1):
                all_poses.append(pose_arrays)
            else:
                print(f"Unexpected shape for document {document['_id']}: {pose_arrays.shape}")
            # print(f'Document {counter}: {pose_arrays.shape}')
        if len(all_poses) < num_of_poses:
            print(f"Only {len(all_poses)} poses found in the database. "
                  f"Please check if the pose detector is running properly.")
            return None
        # Concatenate all the pose arrays to form a single array
        all_poses_stacked = np.stack(all_poses, axis=0)
        print(all_poses_stacked.shape)
        # Determine the number of complete sets of 60
        num_complete_sets = len(all_poses_stacked) // 10

        # Slice the array to only include complete sets of 60
        final_poses = all_poses_stacked[:num_complete_sets * 10]

        # Reshape the array to have the correct final shape (x, 3, 60, 25, 1)
        final_shape = (num_complete_sets, 3, 10, 25, 1)
        final_poses = final_poses.reshape(final_shape)

        training_poses = pre_normalization(final_poses)
        print(training_poses.shape)
        return training_poses

    def store_labeled_pose(self, timestamp, poses, label, past_time=None, version=None,
                           collection_name="labeled_poses"):
        collection = self.get_collection(collection_name)
        # Assuming that poses is already a list of np.arrays with shape (3, 60, 25, 1)
        # Convert each np.array pose to a list before storing in MongoDB
        la_timezone = pytz.timezone('America/Los_Angeles')
        local_timestamp = datetime.now(la_timezone).strftime('%Y-%m-%d %H:%M:%S')  # Readable local timestamp

        documents = []
        for i in range(poses.shape[0]):
            print(poses[i].shape)
            pose_list = poses[i].tolist()  # Convert each (3, 60, 25, 1) pose to a list
            document = {
                "pose": pose_list,
                "label": label,
                "local_time": local_timestamp,
                "service": "Training Service",
                "timestamp": timestamp
            }
            if version is not None:
                document["version"] = version
            if past_time is not None:
                document["past_time"] = past_time
            documents.append(document)

        collection.insert_many(documents)


if __name__ == '__main__':
    # notify_training('Training started')
    # store_training_logs('Mock logging')
    mongodb = MongoDBHandler('mongodb://root:password@128.195.151.182:27017/', 'calit2')
    ts = 1700784151580
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
