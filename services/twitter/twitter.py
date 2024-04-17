import configparser
from datetime import datetime
import pymongo
import tweepy
from flask import Flask, jsonify, render_template, request
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
USAGE_COLLECTION = config["mongodb"]["twitter_usage"]
ADMIN_USERNAME = config["admin"]["username"]
ADMIN_PASSWORD = config["admin"]["password"]

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


def check_auth(username, password):
    """Check if a username and password are valid to view the admin page."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def authenticate():
    """Send a 401 response that enables basic auth."""
    return (
        "Unauthorized access. Please provide valid credentials.",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


def write_usage_log(db, collection, endpoint, method, response_code, response_message):
    db[collection].insert_one(
        {
            "endpoint": endpoint,
            "method": method,
            "time": datetime.now(),
            "response_code": response_code,
            "response_message": response_message,
        }
    )


@app.route("/create_tweet", methods=["POST"])
def create_tweet():
    try:
        db = connect_to_mongodb()
        prediction_collection = db[PREDICTION_COLLECTION]
        entries_to_tweet = prediction_collection.find({"tweeted": False})

        new_tweets = 0
        for entry in entries_to_tweet:
            tweet_text = f"{entry['manufacturer']} {entry['name']} has been approved. Estimated flight numbers:\nSPEED: {int(entry['SPEED'])}\nGLIDE: {int(entry['GLIDE'])}\nTURN : {int(entry['TURN'])}\nFADE : {int(entry['FADE'])}\n\nSee it here: {entry['url']}"

            prediction_collection.update_one(
                {"_id": entry["_id"]}, {"$set": {"tweeted": True}}
            )

            apiv2.create_tweet(text=tweet_text, user_auth=True)
            new_tweets += 1

        message = f"{new_tweets} tweets created successfully."
        write_usage_log(db, USAGE_COLLECTION, "/create_tweet", "POST", 200, message)
        return (
            jsonify({"message": message}),
            200,
        )

    except Exception as e:
        write_usage_log(db, USAGE_COLLECTION, "/create_tweet", "POST", 500, str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/admin", methods=["GET"])
def admin():
    auth = request.authorization

    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

    db = connect_to_mongodb()
    collection = db[USAGE_COLLECTION]

    pipeline = [
        {
            "$group": {
                "_id": "$endpoint",
                "count": {"$sum": 1},
                "last_run": {"$max": "$time"},
            }
        },
    ]

    aggregation_result = list(collection.aggregate(pipeline))

    endpoint_counts = {
        item["_id"]: {"count": item["count"], "last_run": item["last_run"]}
        for item in aggregation_result
    }

    all_entries = list(collection.find({}, {"_id": 0}))

    return render_template(
        "admin.html", endpoint_counts=endpoint_counts, log=all_entries
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004)
