import configparser
import pytest
from datetime import datetime
from unittest.mock import patch

from services.frontend.frontend import (
    app,
    authenticate,
    check_auth,
    connect_to_mongodb,
    format_date,
    prepare_for_table,
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
    with patch("services.prediction.prediction.pymongo.MongoClient") as mock_client:
        connect_to_mongodb()
        mock_client.assert_called_once()


def test_check_auth_valid_credentials():
    username = ADMIN_USERNAME
    password = ADMIN_PASSWORD
    assert check_auth(username, password)


def test_check_auth_invalid_credentials():
    username = "invalid_admin"
    password = "wrong_password"
    assert not check_auth(username, password)


def test_authenticate():
    response = authenticate()
    assert response[1] == 401
    assert response[2]["WWW-Authenticate"] == 'Basic realm="Login Required"'


@pytest.fixture
def sample_input_dict():
    return {
        "name": "Test Disc",
        "approved_date": "Apr 23, 2024",
        "other_field": "value",
    }


def test_prepare_for_table(sample_input_dict):
    result = prepare_for_table(sample_input_dict.copy())

    assert result["approved_date"].strftime("%Y-%m-%d") == "2024-04-23"
    assert result["name"] == "Test Disc"
    assert result["other_field"] == "value"


def test_format_date():
    date_time = datetime(2024, 4, 23, 12, 0)
    result = format_date(date_time)

    assert result == "2024-04-23"


def test_index_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
