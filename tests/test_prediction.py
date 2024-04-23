import configparser
import pytest
from unittest.mock import patch, MagicMock

from services.prediction.prediction import (
    app,
    authenticate,
    check_auth,
    clean_data,
    connect_to_mongodb,
    download_newest_model_from_s3,
    fetch_data,
    load_model,
    make_predictions,
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


def test_verify_api_key_missing(client):
    response = client.post("/predict")
    assert response.status_code == 401
    assert b"API key is missing" in response.data


def test_verify_api_key_invalid(client):
    response = client.post("/predict", headers={"X-API-KEY": "wrong_key"})
    assert response.status_code == 401
    assert b"Invalid API key" in response.data


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


def test_download_newest_model_from_s3():
    with patch("services.prediction.prediction.boto3.client") as mock_s3_client:
        mock_response = {
            "Contents": [{"Key": "model_1.pkl", "LastModified": "2024-04-23T12:00:00Z"}]
        }
        mock_s3_client.return_value.list_objects_v2.return_value = mock_response
        download_newest_model_from_s3("test_bucket")
        mock_s3_client.return_value.download_file.assert_called_once()


def test_fetch_data():
    mock_db = MagicMock()
    mock_scraper_collection = MagicMock()
    mock_prediction_collection = MagicMock()

    mock_db.__getitem__.return_value = mock_scraper_collection
    mock_scraper_collection.find.return_value = [{"url": "test_url"}]
    mock_prediction_collection.find.return_value = [{"url": "test_url"}]
    mock_db.__getitem__.return_value = mock_prediction_collection

    data = fetch_data()
    assert len(data) == 0


def test_load_model():
    with patch("builtins.open", create=True), patch(
        "services.prediction.prediction.joblib.load"
    ) as mock_load:
        load_model()
        mock_load.assert_called_once()


def test_make_predictions():
    mock_model = MagicMock()
    mock_data = {
        "diameter": ["1.0cm"],
        "height": ["1.0cm"],
        "rim_depth": ["1.0cm"],
        "inside_rim_diameter": ["1.0cm"],
        "rim_depth_diameter_ratio": ["1.0"],
        "rim_config": ["test_config"],
    }
    with patch("services.prediction.prediction.load_model") as mock_load_model:
        mock_load_model.return_value = mock_model
        predictions = make_predictions(mock_model, mock_data)
        assert predictions.shape == (1, 11)


def test_clean_data():
    input_dict = {
        "max_weight": "175gr",
        "diameter": "21.2cm",
        "height": "1.5cm",
        "rim_depth": "1.2cm",
        "rim_thickness": "1.5cm",
        "inside_rim_diameter": "1.2cm",
        "rim_depth_diameter_ratio": "10%",
        "flexibility": "Flex",
    }

    cleaned_data = clean_data(input_dict)

    assert cleaned_data["max_weight"] == 175.0
    assert cleaned_data["diameter"] == 21.2
    assert cleaned_data["height"] == 1.5
    assert cleaned_data["rim_depth"] == 1.2
    assert cleaned_data["rim_thickness"] == 1.5
    assert cleaned_data["inside_rim_diameter"] == 1.2
    assert cleaned_data["rim_depth_diameter_ratio"] == 10.0
    assert cleaned_data["flexibility"] == "Flex"


# Note: You can add more tests for other functions and endpoints in a similar fashion.
