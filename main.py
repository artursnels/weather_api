import json
import sqlite3
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from starlette.responses import Response
from pydantic import BaseModel
import requests
from fastapi.responses import JSONResponse


debug = False


weather = "./weather.db"


class Readings(BaseModel):
    token: str
    pressure_pa: Optional[int] = None
    uv_index: Optional[int] = None
    windspeed_ms: Optional[int] = None
    humidity_perc: Optional[int] = None
    temperature_c: Optional[float] = None
    day_night: Optional[str] = None
    air_quality: Optional[str] = None
    is_raining: Optional[bool] = None


app = FastAPI()

allowed_countries = [
    'SE', 'LV'
]

print("Accepting IPs only from following countries: ", end="")
print(*allowed_countries, sep=", ")


@app.post("/upload/")
async def upload_to_db(readings: Readings):
    """


    """
    readings_dict = {}

    for i in readings:
        reading_name = i[0]
        reading = i[1]
        readings_dict[reading_name] = reading

    readings = readings_dict
    timestamp_unix = int(time.time())
    sql = """SELECT * FROM Stations WHERE (uuid) = ?"""
    conn = sqlite3.connect(weather)

    cursor = conn.cursor()
    cursor.execute(sql, (readings["token"],))

    result = cursor.fetchone()

    station_id = result[0]
    country = result[1]
    town = result[2]
    name = result[3]

    sql = """INSERT INTO Readings
             (station_id, pressure_pa, uv_index, windspeed_ms, humidity_perc, temperature_c, day_night, air_quality, is_raining, country, town, name, timestamp_unix)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    cursor.execute(sql, (
        station_id, readings["pressure_pa"], readings["uv_index"], readings["windspeed_ms"], readings["humidity_perc"],
        readings["temperature_c"], readings["day_night"], readings["air_quality"], readings["is_raining"], country,
        town,
        name, timestamp_unix,))
    conn.commit()

    return "Uploaded successfully!"


def allow_country(request: Request):
    if not debug:
        ip = request.client.host
        response = requests.get(f"http://ip-api.com/json/{ip}")
        resp_json = response.json()
        country_code = resp_json['countryCode']
        isp = resp_json["isp"]
        country = resp_json['country']
        if country_code not in allowed_countries:
            print(f"Refused to serve an IP from {country}, ISP: {isp}")
            raise HTTPException(status_code=403, detail="Access restricted.")


@app.middleware("http")
async def check_country_restriction(request: Request, call_next):
    try:
        allow_country(request)
    except HTTPException as e:
        return Response(content=e.detail, status_code=e.status_code)

    response = await call_next(request)
    return response


@app.get("/")
async def root(request: Request):
    return {"message": "Hello World"}


# structure 1: /country/{country}/town/{town} - GETS LATEST

# structure 2: /country/{country}/town/{town}/name/{name} - GETS LATEST

# structure 3: /country/{country}/town/{town}/amount/{amount} - GETS LAST {amount} READINGS

# structure 3: /country/{country}/town/{town}/name/{name}/amount/{amount} - GETS LAST {amount} READINGS

@app.get("/name/{name}")
async def get_data(name: str):
    sql = """
    SELECT * FROM Readings WHERE (name) = ? ORDER BY timestamp_unix DESC LIMIT 1; 
    """
    conn = sqlite3.connect(weather)

    cursor = conn.cursor()
    cursor.execute(sql, (name,))

    result = cursor.fetchone()

    readings_dict = {
        "pressure_pa": result[2],
        "uv_index": result[3],
        "windspeed_ms": result[4],
        "humidity_perc": result[5],
        "temperature_c": result[6],
        "day_night": result[7],
        "air_quality": result[8],
        "is_raining": bool(result[9])
    }

    info_dict = {
        "reading_id": result[0],
        "station_id": result[1],
        "timestamp_unix": result[13],
        "country": result[10],
        "town": result[11],
        "name": result[12]
    }

    response_dict = {
        "info": info_dict,
        "readings": readings_dict
    }


    return JSONResponse(content=response_dict)


@app.get("/country/{country}/town/{town}/name/{name}")
async def say_hello(country: str, town: str, name: str, request: Request):
    return {"message": f"Hello {country}, {town}, {name}"}
