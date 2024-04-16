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


# def prepare_for_table(input_dict: dict) -> dict:
#     """Prepares columns to be sortable items when presented in the table by removing units (gr, %, etc.),
#     converting -0.0 into 0, and making the date string a datetime object.

#     Args:
#         input_dict (dict): "raw" data from MongoDB collection before processing

#     Returns:
#         dict: data in the same structure as it is passed in as with the updated data types
#     """
#     for key, value in input_dict.items():
#         if key in [
#             "max_weight",
#             "diameter",
#             "height",
#             "rim_depth",
#             "rim_thickness",
#             "inside_rim_diameter",
#             "rim_depth_diameter_ratio",
#             "flexibility",
#         ]:
#             try:
#                 value = value.rstrip("grkcm%")
#                 input_dict[key] = float(value)
#             except ValueError:
#                 pass
#         if key in ["TURN"]:
#             try:
#                 if value == -0.0:
#                     input_dict[key] = 0.0 - float(value)
#             except ValueError:
#                 pass
#         if key in "approved_date":
#             date_object = datetime.strptime(value, "%b %d, %Y").date()
#             input_dict[key] = date_object
#     return input_dict


@app.route("/")
def index():
    db = connect_to_mongodb()
    discs_cursor = db[PREDICTION_COLLECTION].find()
    discs = list(discs_cursor)
    # processed_discs = [prepare_for_table(disc) for disc in discs]
    return render_template("index.html", discs=discs)


if __name__ == "__main__":
    app.run()
