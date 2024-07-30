from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa; F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# client = MongoClient(
#     f"mongodb://{app.config['MONGO_USERNAME']}:{app.config['MONGO_PASSWORD']}@localhost")
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service == None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    # abort(500, 'Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"


print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

######################################################################
# INSERT CODE HERE
######################################################################
@app.route("/health", methods=["GET"])
def check_health():
    return jsonify({"status": "OK"}), 200

@app.route("/count", methods=['GET'])
def get_song_count():
    """Return the total number of songs"""
    total_songs = db.songs.count_documents({})
    if total_songs > 0:
        return jsonify({"length": total_songs}), 200
    return {"message": "Internal server error"}, 500

@app.route('/song', methods=['GET'])
def get_all_songs():
    song_list = list(db.songs.find({}))
    for song in song_list:
        rewrite_oid(song)
    if song_list:
        return jsonify({"songs": song_list}), 200
    return {"message": "No songs found"}, 404

@app.route('/song/<int:id>', methods=['GET'])
def retrieve_song(id):
    found_song = db.songs.find_one({"id": id})
    if found_song:
        rewrite_oid(found_song)
        return jsonify(found_song), 200
    return {"message": f"Song with id {id} not found"}, 404

@app.route('/song/<int:id>', methods=['PUT'])
def modify_song(id):
    existing_song = db.songs.find_one({"id": id})
    update_data = parse_json(request.get_json())
    if existing_song:
        result = db.songs.update_one(existing_song, {"$set": update_data})
        if result.modified_count == 0:
            return {"message": "Song found, but no changes made"}, 200
        return jsonify({"updated_id": {"$oid": str(existing_song['_id'])}}), 201
    return {"message": f"Song with id {id} not found"}, 404

@app.route('/song/<int:id>', methods=['DELETE'])
def remove_song(id):
    result = db.songs.delete_one({"id": id})
    if result.deleted_count == 1:
        return {}, 204
    return {"message": f"Song with id {id} not found"}, 404

@app.route('/song', methods=['POST'])
def add_song():
    new_song = parse_json(request.get_json())
    existing_song = db.songs.find_one({"id": new_song['id']})
    if not existing_song:
        result = db.songs.insert_one(new_song)
        return jsonify({"inserted_id": {"$oid": str(result.inserted_id)}}), 201
    return {"Message": f"Song with id {new_song['id']} already present"}, 302