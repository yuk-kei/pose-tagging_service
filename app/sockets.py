from flask import blueprints, current_app
from app import mongodb, socketio

notifications_blueprint = blueprints.Blueprint('notifications', __name__, url_prefix='/api/v1/notifications')
watcher = None


def mongo_watch(collection, operations=None, event='notifications'):
    collection = mongodb.get_collection(collection)

    if operations is None:
        operations = ['insert']
    with collection.watch([{'$match': {'operationType': {'$in': operations}}}]) as stream:
        for change in stream:
            data = change['fullDocument']
            message = data['message']
            socketio.emit(event, message)


@socketio.on('connect')
def on_connect():
    global watcher
    if watcher is None:
        watcher = socketio.start_background_task(
            mongo_watch,
            collection=current_app.config['COLLECTION_NAME'],
            operations=['insert', 'update'],
            event='notifications'
        )
    print('Client connected')


@socketio.on('disconnect')
def on_disconnect():

    print('Client disconnected')
