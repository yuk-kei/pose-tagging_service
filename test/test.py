from pymongo import MongoClient

client = MongoClient(
    'mongodb://root:password@128.195.151.182:27017/?replicaSet=replicaset'
)

db = client['calit2']
db_collection = db['notification']
print(db.get_collection('notification').find_one())
# Perform operations on 'db'
