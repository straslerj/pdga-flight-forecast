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


def write_usage_log(
    db: pymongo.MongoClient,
    collection: str,
    endpoint: str,
    method: str,
    response_code: int,
    response_message: str,
    start_time: datetime.now,
):
    """Writes a log to MongoDB database

    Args:
        db (pymongo.MongoClient): the database to write the log to
        collection (str): the colleciton within the database
        endpoint (str): the endpoint called
        method (str): the ReST method used to call the endpoint
        response_code (int): the response code returned
        response_message (str): the message returned
        start_time (datetime): used to determine the response time of the endpoint
    """
    response_time = (datetime.now() - start_time).total_seconds() * 1000  # milliseconds
    db[collection].insert_one(
        {
            "endpoint": endpoint,
            "method": method,
            "time": datetime.now(),
            "response_code": response_code,
            "response_message": response_message,
            "response_time": response_time,
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
    start_time = datetime.now()
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
    write_usage_log(db, USAGE_COLLECTION, "/", "GET", 200, message, start_time)
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
                "average_time": {
                    "$avg": "$response_time"
                },  # Calculate average response time
            }
        },
    ]

    aggregation_result = list(collection.aggregate(pipeline))

    endpoint_data = {
        item["_id"]: {
            "count": item["count"],
            "last_run": item["last_run"],
            "average_time": (
                round(item["average_time"], 2) if item["average_time"] else 0
            ),  # Round to 2 decimal places
        }
        for item in aggregation_result
    }

    all_entries = list(collection.find({}, {"_id": 0}).sort("time", -1))

    return render_template("admin.html", endpoint_data=endpoint_data, log=all_entries)


if __name__ == "__main__":
    app.run()
