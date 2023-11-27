import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://root:password@128.195.151.182:27017/?replicaSet=replicaset')
    DATABASE_NAME = os.environ.get('DATABASE_NAME', 'calit2')
    COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'notification')
    TRAINING_URL = os.environ.get('TRAINER_URL')


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True


class ProductionConfig(BaseConfig):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': DevelopmentConfig
}
