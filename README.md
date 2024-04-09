# PDGA Flight Forecast

Predicting the flight numbers of discs newly submitted to the PDGA for approval.

[![Docker Build](https://github.com/straslerj/pdga-flight-forecast/actions/workflows/build-docker-containers.yml/badge.svg)](https://github.com/straslerj/pdga-flight-forecast/actions/workflows/build-docker-containers.yml)

## Background

In disc golf, different discs have different flights.

![alt text](assets/stability.png)

These flights (or flight paths) are determined by the physical measurements of the discs. These often get summarized by "flight numbers".

<img src="assets/flight-numbers.png" alt="alt text" width="450" height="400">



Flight numbers are determined in by the manufacturer of the disc through two primary methods: 

1. How do people testing the disc feel that it flies compared to other discs they have thrown.
2. What the physical measurements of the disc suggests.

When a manufacturer makes a new disc they first must submit it to the PDGA for approval, as there are certain constraints a disc must fall within. The PDGA posts the newly approved discs [on their website](https://www.pdga.com/technical-standards/equipment-certification/discs). However, only the disc dimensions are posted, not its flight numbers, leaving many disc golfers anxiously speculating at what the newest discs might fly like.

The goal of this project is to scrape the PDGA website and use a machine leaning model ([developed here](https://github.com/straslerj/disc-golf-flight-numbers)) to predict the flight of the newly submitted discs.