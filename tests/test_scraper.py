import configparser
import pytest
from unittest.mock import patch

from services.scraper.scraper import (
    app,
    capitalize_words_after_last_slash,
    check_auth,
    connect_to_mongodb,
)

config = configparser.ConfigParser()
config.read("config.ini")
ADMIN_USERNAME = config["admin"]["username"]
ADMIN_PASSWORD = config["admin"]["password"]
API_KEY = config["auth"]["api_key"]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_connect_to_mongodb():
    with patch("pymongo.MongoClient") as mock_client:
        connect_to_mongodb()
        mock_client.assert_called_once()


def test_verify_api_key_missing(client):
    response = client.get("/last_scraped")
    assert response.status_code == 401
    assert b"API key is missing" in response.data


def test_verify_api_key_invalid(client):
    response = client.get("/last_scraped", headers={"X-API-KEY": "wrong_key"})
    assert response.status_code == 401
    assert b"Invalid API key" in response.data


def test_get_last_scraped(client):
    response = client.get("/last_scraped", headers={"X-API-KEY": API_KEY})
    assert response.status_code == 200
    assert b"Scrape and store endpoint has not been called yet." in response.data


def test_admin_unauthorized(client):
    response = client.get("/admin")
    assert response.status_code == 401
    assert b"Unauthorized access. Please provide valid credentials." in response.data


def test_scrape_and_store_failure(client):
    with patch(
        "services.scraper.scraper.connect_to_mongodb"
    ) as mock_connect_to_mongodb, patch(
        "services.scraper.scraper.requests.get"
    ) as mock_requests_get:

        mock_connect_to_mongodb.side_effect = Exception("MongoDB error")
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.content = b"<html></html>"

        response = client.post("/scrape_and_store", headers={"X-API-KEY": API_KEY})

        assert response.status_code == 500
        assert b"MongoDB error" in response.data


def test_check_auth_valid_credentials():
    username = ADMIN_USERNAME
    password = ADMIN_PASSWORD
    assert check_auth(username, password) == True


def test_check_auth_invalid_username():
    username = "invalid_admin"
    password = "password123"
    assert check_auth(username, password) == False


def test_check_auth_invalid_password():
    username = "admin"
    password = "wrong_password"
    assert check_auth(username, password) == False


def test_check_auth_invalid_credentials():
    username = "invalid_admin"
    password = "wrong_password"
    assert check_auth(username, password) == False


def test_capitalize_words_after_last_slash():
    url = "https://www.pdga.com/test-disc-name"
    result = capitalize_words_after_last_slash(url)
    assert result == "Test Disc Name"
