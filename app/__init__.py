import os

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

from .database import MongoDBHandler

load_dotenv()
socketio = SocketIO(cors_allowed_origins='*')
mongodb = MongoDBHandler(os.environ.get('MONGODB_URI'),
                         os.environ.get('DATABASE_NAME' ))


# mongodb = MongoDBHandler(os.environ.get('MONGODB_URI'), os.environ.get('DATABASE_NAME'))
def create_app():
    """
    The create_app function wraps the creation of a new Flask application,

    :return: The flask app object
    :doc-author: Yukkei
    """
    app = Flask(__name__)

    CORS(app)  # Allow CORS for all domains on all routes
    app.config.from_object('config.DevelopmentConfig')

    from .sockets import notifications_blueprint
    app.register_blueprint(notifications_blueprint)
    socketio.init_app(app)
    from .routes import trigger_blueprint
    app.register_blueprint(trigger_blueprint)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app, socketio


