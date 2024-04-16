import configparser
from datetime import datetime
import pymongo

from flask import Flask, render_template


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

app = Flask(__name__)


def connect_to_mongodb() -> pymongo.MongoClient:
    """Makes connection to MongoDB

    Returns:
        MongoClient: Instance of MongoDB
    """

    client = pymongo.MongoClient(URI)

    db = client[DB_NAME]
    return db


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

    return render_template("index.html", discs=discs)


if __name__ == "__main__":
    app.run()
