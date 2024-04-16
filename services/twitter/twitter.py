import configparser
import pymongo
import tweepy
from flask import Flask, jsonify, request
from functools import wraps


"""
Twitter service which publishes the newly made predictions to the Twitter feed.
"""
config = configparser.ConfigParser()
config.read("config.ini")

API_KEY = config["twitter"]["api_key"]
API_KEY_SECRET = config["twitter"]["api_key_secret"]
ACCESS_TOKEN = config["twitter"]["access_token"]
ACCESS_TOKEN_SECRET = config["twitter"]["access_token_secret"]
URI = config["mongodb"]["uri"]
DB_NAME = config["mongodb"]["db_name"]
PREDICTION_COLLECTION = config["mongodb"]["prediction_collection"]

app = Flask(__name__)

apiv2 = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
)


def connect_to_mongodb() -> pymongo.MongoClient:
    """Makes connection to MongoDB

    Returns:
        MongoClient: Instance of MongoDB
    """

    client = pymongo.MongoClient(URI)

    db = client[DB_NAME]
    return db


def verify_api_key(func):
    """Used to verify access across APIs"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        provided_api_key = request.headers.get("X-API-KEY")
        if not provided_api_key:
            return jsonify({"message": "API key is missing"}), 401

        config_api_key = config["auth"]["api_key"]
        if provided_api_key != config_api_key:
            return jsonify({"message": "Invalid API key"}), 401

        return func(*args, **kwargs)

    return wrapper


@app.route("/create_tweet", methods=["POST"])
def create_tweet():
    try:
        db = connect_to_mongodb()
        prediction_collection = db[PREDICTION_COLLECTION]
        entries_to_tweet = prediction_collection.find({"tweeted": False})

        new_tweets = 0
        for entry in entries_to_tweet:
            tweet_text = f"{entry['manufacturer']} {entry['name']} has been approved. Estimated flight numbers:\nSPEED: {entry['SPEED']}\nGLIDE: {entry['GLIDE']}\nTURN : {entry['TURN']}\nFADE : {entry['FADE']}\n\nSee it here: {entry['url']}"

            prediction_collection.update_one(
                {"_id": entry["_id"]}, {"$set": {"tweeted": True}}
            )

            apiv2.create_tweet(text=tweet_text, user_auth=True)
            new_tweets += 1
        return (
            jsonify({"message": f"{new_tweets} tweets created successfully"}),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004)
