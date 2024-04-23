import configparser
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from services.twitter.twitter import (
    app,
    authenticate,
    check_auth,
    connect_to_mongodb,
    verify_api_key,
    write_usage_log,
)

config = configparser.ConfigParser()
config.read("config.ini")
ADMIN_USERNAME = config["admin"]["username"]
ADMIN_PASSWORD = config["admin"]["password"]
API_KEY = config["auth"]["api_key"]
URI = config["mongodb"]["uri"]
DB_NAME = config["mongodb"]["db_name"]
PREDICTION_COLLECTION = config["mongodb"]["prediction_collection"]
USAGE_COLLECTION = config["mongodb"]["twitter_usage"]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_check_auth_valid_credentials():
    username = ADMIN_USERNAME
    password = ADMIN_PASSWORD
    assert check_auth(username, password)


def test_check_auth_invalid_credentials():
    username = "invalid_admin"
    password = "wrong_password"
    assert not check_auth(username, password)


def test_verify_api_key_missing(client):
    response = client.post("/create_tweet")
    assert response.status_code == 401
    assert b"API key is missing" in response.data


def test_verify_api_key_invalid(client):
    response = client.post("/create_tweet", headers={"X-API-KEY": "wrong_key"})
    assert response.status_code == 401
    assert b"Invalid API key" in response.data


def test_write_usage_log():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection

    endpoint = "/create_tweet"
    method = "POST"
    response_code = 200
    response_message = "Success"
    start_time = datetime.now()

    write_usage_log(
        mock_db,
        USAGE_COLLECTION,
        endpoint,
        method,
        response_code,
        response_message,
        start_time,
    )

    mock_collection.insert_one.assert_called_once()


def test_create_tweet(client):
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    mock_find = mock_collection.find.return_value
    mock_find.__iter__.return_value = [
        {
            "_id": "123",
            "manufacturer": "TestManufacturer",
            "name": "TestName",
            "SPEED": "10",
            "GLIDE": "5",
            "TURN": "2",
            "FADE": "4",
            "url": "http://test.url",
            "tweeted": False,
        }
    ].__iter__()

    with patch("services.twitter.twitter.connect_to_mongodb", return_value=mock_db):
        with patch("services.twitter.twitter.apiv2.create_tweet") as mock_create_tweet:
            response = client.post("/create_tweet", headers={"X-API-KEY": API_KEY})
            assert response.status_code == 200
            assert response.json["message"] == "1 tweets created successfully."
            mock_create_tweet.assert_called_once()
