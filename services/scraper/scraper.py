import configparser
import pymongo
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, jsonify
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

app = Flask(__name__)

last_scraped = None


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


def connect_to_mongodb() -> pymongo.MongoClient:
    """Makes connection to MongoDB

    Returns:
        MongoClient: Instance of MongoDB
    """

    client = pymongo.MongoClient(URI)

    db = client[DB_NAME]
    return db


@app.route("/last_scraped", methods=["GET"])
def get_last_scraped():
    global last_scraped

    if last_scraped:
        return (
            jsonify({"last_scraped": last_scraped.strftime("%Y-%m-%d %H:%M:%S")}),
            200,
        )
    else:
        return (
            jsonify({"message": "Scrape and store endpoint has not been called yet."}),
            200,
        )


@app.route("/scrape_and_store", methods=["POST"])
def scrape_and_store():
    """Scrapes the PDGA website and adds the new discs to the database

    Returns:
        JSON: 200 when successful
              500 when error
    """
    global last_scraped
    last_scraped = datetime.now()
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

        print("Connecting to MongoDB...")
        db = connect_to_mongodb()
        print("Connected to MongoDB")

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

        return (
            jsonify(
                {
                    "message": f"Data scraped and stored successfully. {new_entries} discs added to {DB_NAME}/{COLLECTION}."
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
