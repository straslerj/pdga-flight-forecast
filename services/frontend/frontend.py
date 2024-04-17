import configparser
from datetime import datetime
import pymongo

from flask import Flask, render_template, request


"""
Prediction service which pulls in a model from an S3 bucket, makes predictions on data
from the database created by the scraper service, and then uploads the predictions to 
a new databse collection to be displayed on the frontend.
"""
config = configparser.ConfigParser()
config.read("config.ini")
URI = config["mongodb"]["uri"]
DB_NAME = config["mongodb"]["db_name"]
PREDICTION_COLLECTION = config["mongodb"]["prediction_collection"]
USAGE_COLLECTION = config["mongodb"]["frontend_usage"]
ADMIN_USERNAME = config["admin"]["username"]
ADMIN_PASSWORD = config["admin"]["password"]

app = Flask(__name__)


def connect_to_mongodb() -> pymongo.MongoClient:
    """Makes connection to MongoDB

    Returns:
        MongoClient: Instance of MongoDB
    """

    client = pymongo.MongoClient(URI)

    db = client[DB_NAME]
    return db


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


def prepare_for_table(input_dict: dict) -> dict:
    """Prepares date field to be sortable items by making the date string a datetime object.

    Args:
        input_dict (dict): "raw" data from MongoDB collection before processing

    Returns:
        dict: data in the same structure as it is passed in as with the updated data type
    """
    for key, value in input_dict.items():

        if key in "approved_date":
            date_object = datetime.strptime(value, "%b %d, %Y").date()
            input_dict[key] = date_object
    return input_dict


def format_date(date_time) -> str:
    """Formats date-time to only display the date portion

    Args:
        date_time (datetime): The datetime object to be formatted

    Returns:
        str: Formatted date string
    """
    return date_time.strftime("%Y-%m-%d")


@app.route("/")
def index():
    db = connect_to_mongodb()
    discs_cursor = db[PREDICTION_COLLECTION].find()

    discs = [
        (
            {**disc, "approved_date": format_date(disc["approved_date"])}
            if "approved_date" in disc and isinstance(disc["approved_date"], datetime)
            else disc
        )
        for disc in discs_cursor
    ]

    message = f"Number of discs: {len(discs)}"
    write_usage_log(db, USAGE_COLLECTION, "/", "GET", 200, message)
    return render_template("index.html", discs=discs)


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

    all_entries = list(collection.find({}, {"_id": 0}).sort("time", -1))

    return render_template(
        "admin.html", endpoint_counts=endpoint_counts, log=all_entries
    )


if __name__ == "__main__":
    app.run()
