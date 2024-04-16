import configparser
import pymongo
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from functools import wraps
from urllib.parse import urlparse

"""
Scraper service which gets the new discs from the PDGA approved discs list.

PDGA website: https://www.pdga.com/technical-standards/equipment-certification/discs
"""

config = configparser.ConfigParser()
config.read("config.ini")
URI = config["mongodb"]["uri"]
DB_NAME = config["mongodb"]["db_name"]
COLLECTION = config["mongodb"]["scraper_collection"]
USAGE_COLLECTION = config["mongodb"]["scraper_usage"]
ADMIN_USERNAME = config["admin"]["username"]
ADMIN_PASSWORD = config["admin"]["password"]

app = Flask(__name__)

last_scraped = None


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


def capitalize_words_after_last_slash(url: str) -> str:
    """Disc name is not included in the parsed HTML. This method extracts it from the URL and formats it nicely.

    Args:
        url (str): URL to disc specifications

    Returns:
        str: Name of the disc appropriately formatted (capitalized, no hyphens)
    """
    parsed_url = urlparse(url)
    path = parsed_url.path
    parts = path.split("/")
    last_part = parts[-1]
    words = last_part.split("-")
    capitalized_words = " ".join(word.capitalize() for word in words)
    return capitalized_words


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


@app.route("/last_scraped", methods=["GET"])
@verify_api_key
def get_last_scraped():
    global last_scraped
    db = connect_to_mongodb()
    if last_scraped:
        message = last_scraped.strftime("%Y-%m-%d %H:%M:%S")
        write_usage_log(db, USAGE_COLLECTION, "/last_scraped", "GET", 200, message)

        return (
            jsonify({"last_scraped": message}),
            200,
        )
    else:
        message = "Scrape and store endpoint has not been called yet."
        write_usage_log(db, USAGE_COLLECTION, "/last_scraped", "GET", 200, message)
        return (
            jsonify({"message": message}),
            200,
        )


@app.route("/scrape_and_store", methods=["POST"])
@verify_api_key
def scrape_and_store():
    """Scrapes the PDGA website and adds the new discs to the database

    Returns:
        JSON: 200 when successful
              500 when error
    """
    global last_scraped
    last_scraped = datetime.now()
    try:
        print("Connecting to MongoDB...")
        db = connect_to_mongodb()
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Error trying to connect to MongoDB: {e}")
        return jsonify({"error": str(e)}), 500
    try:
        print("Parsing HTML...")
        base_url = "https://www.pdga.com"
        url = base_url + "/technical-standards/equipment-certification/discs"

        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        links = soup.find_all(
            "a",
            href=lambda href: href
            and href.startswith("/technical-standards/equipment-certification/discs"),
        )

        urls = [base_url + link.get("href") for link in links]
        print("Parsed HTML")

        new_entries = 0
        for url in urls:
            if (
                "?" not in url and "=" not in url
            ):  # There are some URLs that are not to discs. This generally takes care of them
                response = requests.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    try:
                        # Extract relevant information
                        manufacturer = (
                            soup.find(
                                "div", class_="views-field-field-equipment-manuf-ref"
                            )
                            .find("span")
                            .text.strip()
                        )
                        approved_date = soup.find(
                            "span", class_="date-display-single"
                        ).text.strip()
                        max_weight = (
                            soup.find("div", class_="views-field-field-disc-max-weight")
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        diameter = (
                            soup.find(
                                "div", class_="views-field-field-disc-outside-diameter"
                            )
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        height = (
                            soup.find("div", class_="views-field-field-disc-height")
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        rim_depth = (
                            soup.find("div", class_="views-field-field-disc-rim-depth")
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        rim_thickness = (
                            soup.find(
                                "div", class_="views-field-field-disc-rim-thickness"
                            )
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        inside_rim_diameter = (
                            soup.find(
                                "div",
                                class_="views-field-field-disc-inside-rim-diameter",
                            )
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        rim_depth_diameter_ratio = (
                            soup.find(
                                "div",
                                class_="views-field-field-disc-depth-diameter-ratio",
                            )
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        rim_config = (
                            soup.find("div", class_="views-field-field-disc-rim-config")
                            .find("span", class_="field-content")
                            .text.strip()
                        )
                        flexibility = (
                            soup.find(
                                "div", class_="views-field-field-disc-flexibility"
                            )
                            .find("span", class_="field-content")
                            .text.strip()
                        )

                        existing_doc = db[COLLECTION].find_one({"url": url})

                        if (
                            existing_doc is None
                        ):  # Ensures there is no duplicates being added
                            db[COLLECTION].insert_one(
                                {
                                    "url": url,
                                    "manufacturer": manufacturer,
                                    "name": capitalize_words_after_last_slash(url),
                                    "approved_date": approved_date,
                                    "max_weight": max_weight,
                                    "diameter": diameter,
                                    "height": height,
                                    "rim_depth": rim_depth,
                                    "rim_thickness": rim_thickness,
                                    "inside_rim_diameter": inside_rim_diameter,
                                    "rim_depth_diameter_ratio": rim_depth_diameter_ratio,
                                    "rim_config": rim_config,
                                    "flexibility": flexibility,
                                }
                            )
                            print(f"Successfully inserted {url}")
                            new_entries += 1
                    except Exception as e:
                        print(f"Error occured for url {url}: {e}")

        global preds_run
        preds_run = False
        if new_entries > 0:
            preds_run = True
            url = config["urls"]["prediction"]
            headers = {"X-API-KEY": config["auth"]["api_key"]}
            try:
                response = requests.post(url, headers=headers)
                print(f"Prediction service ran: {response}")
                if response.status_code == 401:
                    print("Unauthorized: Invalid API key")
                elif response.status_code != 200:
                    print(f"Error: {response.json()}")
            except Exception as e:
                print(
                    f"The prediction service was triggered but there was an error in running it: {e}"
                )

        message = f"Data scraped and stored successfully. {new_entries} discs added to {DB_NAME}/{COLLECTION}. {'Prediction service triggered.' if preds_run else ''}"
        write_usage_log(db, USAGE_COLLECTION, "/scrape_and_store", "POST", 200, message)
        return (
            jsonify({"message": message}),
            200,
        )
    except Exception as e:
        write_usage_log(db, USAGE_COLLECTION, "/scrape_and_store", "POST", 500, str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/admin", methods=["GET"])
def admin():
    auth = request.authorization

    # Check if the provided credentials match the admin credentials
    if not auth or not check_auth(auth.username, auth.password):
        # If the credentials are invalid, ask for authentication
        return authenticate()

    db = connect_to_mongodb()
    collection = db[USAGE_COLLECTION]

    # Get the number of times each endpoint was called
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

    # Convert the aggregation result to a dictionary with endpoints as keys
    endpoint_counts = {
        item["_id"]: {"count": item["count"], "last_run": item["last_run"]}
        for item in aggregation_result
    }

    # Get all entries in the database
    all_entries = list(collection.find({}, {"_id": 0}))

    return render_template(
        "admin.html", endpoint_counts=endpoint_counts, log=all_entries
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
