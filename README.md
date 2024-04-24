# PDGA Flight Forecast

Predicting the flight numbers of discs newly submitted to the PDGA for approval.

[![Docker Build](https://github.com/straslerj/pdga-flight-forecast/actions/workflows/build-docker-containers.yml/badge.svg)](https://github.com/straslerj/pdga-flight-forecast/actions/workflows/build-docker-containers.yml)

## Background

In disc golf, different discs have different flights:

![stability-diagram](assets/stability.png)

These flights (or flight paths) are determined by the physical measurements of the discs. These often get summarized by "flight numbers":

<img src="assets/flight-numbers.png" alt="flight-number-diagram" width="450" height="400">



Flight numbers are determined in by the manufacturer of the disc through two primary methods: 

1. How do people testing the disc feel that it flies compared to other discs they have thrown.
2. What the physical measurements of the disc suggests.

When a manufacturer makes a new disc they first must submit it to the PDGA for approval, as there are certain constraints a disc must fall within. The PDGA posts the newly approved discs [on their website](https://www.pdga.com/technical-standards/equipment-certification/discs). However, only the disc dimensions are posted, not its flight numbers, leaving many disc golfers anxiously speculating at what the newest discs might fly like.

The goal of this project is to scrape the PDGA website and use a machine leaning model ([developed here](https://github.com/straslerj/disc-golf-flight-numbers)) to predict the flight of the newly submitted discs.

## Overview

This project scrapes the PDGA site daily to check for newly approved discs. Upon finding newly approved discs, the discs' measurements are scraped from the PDGA website for a machine learning model to use to predict the flight numbers for the newly approved discs. New predictions get posted to [X (Twitter)](https://twitter.com/flight_forecast) and to [pdga.jakestrasler.com](https://pdga.jakestrasler.com).

## Architecture

![architecture-diagram](assets/architecture.png)

This system deploys three Dockerized ReST services to Azure Container Apps. Another service, the front end, is deployed on PythonAnywhere and hosted using Cloudflare. These services read and/or write to mongoDB collections. The scraping service is kicked off daily by a CRON job with makes a call to the web scraper, which automatically kicks off the full system if new discs are added.

Services are automatically updated with the most recent push to `main` using a Github workflow that builds each Docker container and pushes it to Docker Hub.

## Installation

### Local 

 1. Clone this repository.
 2. Create a configuration file: `config.ini` like such with your values (which you will need to get from, for example, the Twitter API, which requires you make an account):
    ```
    [mongodb]
    uri 
    db_name 
    scraper_collection 
    prediction_collection 
    scraper_usage 
    prediction_usage 
    twitter_usage 
    frontend_usage 

    [tebi]
    access_key 
    secret_key 
    bucket_name 
    endpoint_url

    [twitter]
    api_key 
    api_key_secret 
    client_id 
    client_secret 
    access_token 
    access_token_secret 
    bearer_token 

    [auth]
    api_key 

    [urls]
    prediction 
    twitter 

    [admin]
    username 
    password 
    ```
3. Ensure basic setup is met by running the unit tests: from the root directory,`pytest`
4. There are four services, each of which are run independently. To run them, navigate to `services/<service of choice>/` and run the `.py` script in that directory just as you would any other Python script: `<script>.py`.
5. Running a service will make it accessible through local endpoints.

### Using Docker

The Docker images for each service can be created using each service's Dockerfile, found in the directory of each service: `docker build -t <image name> .` and then run: `docker run -p 3000:3000 <image name>`.


## API Details

All endpoints are secured and not accessible without a service API key except for the landing page of the front end. Administrative endpoints are username and password protected.

### All Services

#### `/admin`

 - **Description:** Shows administrative information for the specific service.
 - **Methods:** GET
 - **Returns:**
   - `200`
     - Renders HTML displaying administrative information.


#### Attempt to Call Without API Key

 - **Methods:** GET, POST
 - **Returns:**
   - `401`
     - Message:
       - `"API key is missing"`

#### Attempt to Call With Erroneous API Key

 - **Methods:** GET, POST
 - **Returns:**
   - `401`
     - Message:
       - `"Invalid API key"`


### Web Scraper

#### `/last_scraped`

 - **Description:** Gets the last time the scraping endpoint was called.
- **Methods:** GET
- **Returns:**
  - `200`
    - Message:
      - `"Scrape and store endpoint has not been called yet."`
      - `<datetime when scrape and store endpoint last called>`

#### `/scrape_and_store`

 - **Description:** Scrapes the PDGA website to find newly approved discs.
 - **Methods:** POST
 - **Returns:**
   - `200`
     - Message:
       - `"Data scraped and stored successfully. <int> discs added to <db/collection>."`
         - If new discs added, it appends `"Prediction service triggered."`
   - `500`
     - Message:
       - `<error message>`

### Prediction

#### `/predict`

 - **Description:** Uses the current model to predict on new disc measurements.
 - **Methods:** POST
 - **Returns:**
   - `200`
     - Message:
       - `"<count of new predictions> predictions uploaded successfully to <db/collection>"`
   - `500`
     - Message:
       - `<error message>`

### X / Twitter

#### `/create_tweet`

 - **Description:** Creates tweets for the newly-predicted-for discs.
 - **Methods:** POST
 - **Returns:**
   - `200`
     - Message:
       - `"<count of new tweets> tweets created successfully."`
   - `500`
     - Message:
       - `<error message>`


### Front End

#### `/`

 - **Description:** Returns a list of all the discs that have been predicted on to date.
 - **Methods:** GET
 - **Returns:**
   - `200`
     - Renders HTML displaying newly approved disc information and flight number predictions.