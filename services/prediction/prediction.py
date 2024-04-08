import boto3
import configparser
import joblib
import numpy as np
import pandas as pd
import pymongo
import os
import re

from flask import Flask, jsonify


"""
Prediction service which pulls in a model from an S3 bucket, makes predictions on data
from the database created by the scraper service, and then uploads the predictions to 
a new databse collection to be displayed on the frontend.
"""
config = configparser.ConfigParser()
config.read("config.ini")
URI = config["mongodb"]["uri"]
DB_NAME = config["mongodb"]["db_name"]
SCRAPER_COLLECTION = config["mongodb"]["scraper_collection"]
PREDICTION_COLLECTION = config["mongodb"]["prediction_collection"]
ACCESS_KEY = config["tebi"]["access_key"]
SECRET_KEY = config["tebi"]["secret_key"]
ENDPOINT_URL = config["tebi"]["endpoint_url"]
BUCKET_NAME = config["tebi"]["bucket_name"]
LOCAL_MODEL_NAME = "model.pkl"

app = Flask(__name__)


def connect_to_mongodb() -> pymongo.MongoClient:
    """Makes connection to MongoDB

    Returns:
        MongoClient: Instance of MongoDB
    """

    client = pymongo.MongoClient(URI)

    db = client[DB_NAME]
    return db


def download_newest_model_from_s3(bucket_name: str) -> str:
    """Pulls in the latest model from the S3 bucket

    Args:
        bucket_name (str): name of the bucket to pull from

    Returns:
        str: name of the newest model
    """
    s3 = boto3.client(
        service_name="s3",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        endpoint_url=ENDPOINT_URL,
    )
    response = s3.list_objects_v2(Bucket=bucket_name)
    newest_model = max(response["Contents"], key=lambda x: x["LastModified"])
    s3.download_file(bucket_name, newest_model["Key"], LOCAL_MODEL_NAME)
    return newest_model["Key"]


def fetch_data() -> list:
    """Filters the scraped disc collection to just the discs that haven't been updated yet (basically getting any new data)
    and returns just those that have not been predicted on yet.

    Returns:
        list: list containing only data for the discs that need to be predicted on
    """
    db = connect_to_mongodb()
    scraper_collection = db[SCRAPER_COLLECTION]
    prediction_collection = db[PREDICTION_COLLECTION]

    scraper_data = list(scraper_collection.find())
    prediction_urls = {
        item["url"] for item in prediction_collection.find({}, {"url": 1})
    }

    filtered_data = []
    for item in scraper_data:
        if item["url"] not in prediction_urls:
            filtered_data.append(item)

    return filtered_data


def fetch_model() -> None:
    """Pulls in the most recent model from the S3 bucket if the model does not already exist"""
    if not os.path.exists(LOCAL_MODEL_NAME):
        download_newest_model_from_s3(BUCKET_NAME)


def load_model():
    """Loads in the model object from the S3 bucket

    Returns:
        model: scikit-learn model object
    """
    with open(LOCAL_MODEL_NAME, "rb") as file:
        model = joblib.load(file)
    return model


def extract_numbers(value: str) -> str:
    """Removes units from data pieces in order to make them numeric.

    e.g., 1.5cm -> 1.5

    Args:
        value (str): string before preprocessing e.g., 1.5cm

    Returns:
        str: string after preprocessing e.g., 1.5 or None if string does not contain numbers
    """
    numbers = re.findall(r"\d+\.\d+|\d+", value)
    if numbers:
        unit_removed = re.sub(r"\D*$", "", value)  # check for unit
        return unit_removed
    else:
        return None


def make_predictions(model, data: pd.DataFrame) -> pd.DataFrame:
    """Performs predictions on unseen data

    Args:
        model (sklearn): scikit-learn model object
        data (DataFrame): DataFrame containing feature values

    Returns:
        DataFrame: DataFrame including feature values, other disc information such as url, and the predicted speed, glide, turn, and fade
    """
    model = load_model()
    df = pd.DataFrame(data)
    X = df[
        [
            "diameter",
            "height",
            "rim_depth",
            "inside_rim_diameter",
            "rim_depth_diameter_ratio",
            "rim_config",
        ]
    ]
    X.columns = [
        "DIAMETER (cm)",
        "HEIGHT (cm)",
        "RIM DEPTH (cm)",
        "INSIDE RIM DIAMETER (cm)",
        "RIM DEPTH / DIAMETER RATION (%)",
        "RIM CONFIGURATION",
    ]

    for column in X.columns:
        X[column] = X[column].apply(extract_numbers)

    predictions = model.predict(X)

    predictions = np.round(predictions)

    df_predictions = pd.DataFrame(
        predictions, columns=["SPEED", "GLIDE", "TURN", "FADE"]
    )

    df = pd.concat([df, df_predictions], axis=1)
    return df


def upload_predictions_to_mongodb(predictions: dict, collection_name: str) -> None:
    """Uploads the new predictions to MongoDB collection

    Args:
        predictions (dict): dictionary of the data to be inserted into MongoDB
        collection_name (str): name of the collection where the predictions should be inserted
    """
    db = connect_to_mongodb()
    collection = db[collection_name]
    collection.insert_many(predictions)


@app.route("/predict", methods=["GET"])
def predict():
    data = fetch_data()
    if len(data) == 0:
        return jsonify({"message": "No new discs to predict for."})

    fetch_model()
    model = load_model()

    data = make_predictions(model, data)  # type(make_prediction(x, y)) == DataFrame

    mongo_data = data.to_dict(orient="records")

    upload_predictions_to_mongodb(mongo_data, PREDICTION_COLLECTION)

    if os.path.exists(LOCAL_MODEL_NAME):
        os.remove(LOCAL_MODEL_NAME)
        print(f"File '{LOCAL_MODEL_NAME}' removed successfully.")

    return jsonify(
        {
            "message": f"{len(mongo_data)} predictions uploaded successfully to {PREDICTION_COLLECTION}"
        }
    )


if __name__ == "__main__":
    app.run(port=8002)