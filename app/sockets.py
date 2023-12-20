import time

from flask import blueprints, current_app
from app import mongodb, socketio

notifications_blueprint = blueprints.Blueprint('notifications', __name__, url_prefix='/api/v1/notifications')
watcher = None


def mongo_watch(collection, operations=None, event='notifications'):
    print('Starting watcher')
    collection = mongodb.get_collection(collection)


    timestamp = int(time.time() * 1000)
    if operations is None:
        operations = ['insert']

    with collection.watch([{'$match': {'operationType': {'$in': operations}}}]) as stream:
        for change in stream:
            data = change['fullDocument']
            doc_timestamp = data['timestamp']
            curr_timestamp = int(time.time() * 1000)
            print((curr_timestamp - doc_timestamp)/1000)
            if doc_timestamp == timestamp:
                message = curr_timestamp - int(doc_timestamp)
                socketio.emit(event, message)
                timestamp = curr_timestamp


@socketio.on('connect')
def on_connect():
    global watcher
    if watcher is None:
        watcher = socketio.start_background_task(
            mongo_watch,
            # collection=current_app.config['COLLECTION_NAME'],
            collection="results",
            operations=['insert', 'update'],
            event='notifications'
        )
    print('Client connected')


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')
