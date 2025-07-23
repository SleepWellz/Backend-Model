# Backend-Model

## Backend API
### This version ran on Python 3.10.12
### 8GB of RAM is the minimum you need to run the model smoothly 

## Model Endpoints
### 1. /apnea_csv
###     This endpoint is dedicated to handle csv file only
###     payload: csv file

### 2. /apnea_edf
###     This endpoint is dedicated to handle edf file only
###     payload: edf file

## How To Run
### 1. Install all requirements including database and libraries
### 2. Run python run.py on terminal

## Note!!!
### You can only hit the same the same endpoint once at a time
### Tensorflow library is not able to run paralel with the same model
### Queue is needed for the next development stage