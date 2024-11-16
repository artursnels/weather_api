import json
import random
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

is_raining_name = "is_raining"
pressure_name = "pressure_pa"
uv_index_name = "uv_index"
windspeed_name = "windspeed_ms"
humidity_name = "humidity_perc"
temperature_name = "temperature_c"
is_day_name = "is_day"
air_quality_name = "air_quality"


class Readings(BaseModel):
    token: str
    pressure_pa: Optional[int] = None
    uv_index: Optional[int] = None
    windspeed_ms: Optional[int] = None
    humidity_perc: Optional[int] = None
    temperature_c: Optional[float] = None
    is_day: Optional[bool] = None
    air_quality: Optional[str] = None
    is_raining: Optional[bool] = None


app = FastAPI()



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

    #########################
    #        CHECKS         #
    #########################

    errors = []

    if readings[is_raining_name] not in (1, 0, None):
        errors.append(f"Error: {is_raining_name} can only be 1 (true), 0 (false), or null")
        readings[is_raining_name] = None

    if readings[pressure_name] is not None and not (87_000 <= readings[pressure_name] <= 108_500):
        errors.append(f"Error: {pressure_name} must be within the range of 87,000 and 108,500 pascals")
        readings[pressure_name] = None

    if readings[uv_index_name] is not None and not (0 <= readings[uv_index_name] <= 25):
        errors.append(f"Error: {uv_index_name} must be within the range of 0 and 25")
        readings[uv_index_name] = None

    if readings[humidity_name] is not None and not (0 <= readings[humidity_name] <= 100):
        errors.append(f"Error: {humidity_name} must be within the range of 0 and 100 percent")
        readings[humidity_name] = None

    if readings[temperature_name] is not None and not (-90 <= readings[temperature_name] <= 60):
        errors.append(f"Error: {temperature_name} must be within the range of -90 and 60 degrees celsius")
        readings[temperature_name] = None

    if readings[is_day_name] not in (1, 0, None):
        errors.append(f"Error: {is_day_name} can only be 1 (true), 0 (false), or null")
        readings[is_day_name] = None

    if readings[windspeed_name] is not None and not (0 <= readings[windspeed_name] <= 115):
        errors.append(f"Error: {windspeed_name} can only be within the range of 0 and 115 meters per second")
        readings[windspeed_name] = None

    if readings[air_quality_name] is not None and readings[air_quality_name].lower() not in ("good", "moderate", "bad"):
        errors.append(
            f"Error: {air_quality_name} only accepts values 'good', 'moderate', and 'bad'. Qualitative data coming at a later date!")
        readings[air_quality_name] = None

    timestamp_unix = int(time.time())
    sql = """SELECT * FROM Stations WHERE (uuid) = ?"""
    conn = sqlite3.connect(weather)

    cursor = conn.cursor()
    cursor.execute(sql, (readings["token"],))

    result = cursor.fetchone()

    if result is None:
        raise HTTPException(status_code=403, detail={"message": "Invalid token!"})

    station_id = result[0]
    country = result[1]
    town = result[2]
    name = result[3]

    sql = f"""INSERT INTO Readings
             (station_id, {pressure_name}, {uv_index_name}, {windspeed_name}, {humidity_name}, {temperature_name}, {is_day_name}, {air_quality_name}, {is_raining_name}, country, town, name, timestamp_unix)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    cursor.execute(sql, (
        station_id, readings["pressure_pa"], readings["uv_index"], readings["windspeed_ms"], readings["humidity_perc"],
        readings["temperature_c"], readings["is_day"], readings["air_quality"], readings["is_raining"], country,
        town,
        name, timestamp_unix,))
    conn.commit()



    returnable = {
        "status": "Uploaded successfully!"
    }
    if len(errors) > 0:
        returnable["status"] += " However, there were some issues"
        returnable["errors"] = errors


    return JSONResponse(content=returnable, status_code=201)




"""

allowed_countries = [
    'SE', 'LV'
]

print("Accepting IPs only from following countries: ", end="")
print(*allowed_countries, sep=", ")


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
# ddd
"""






def get_from_db(query: str, values: tuple):

    conn = sqlite3.connect(weather)
    cursor = conn.cursor()
    cursor.execute(query, values)
    results = cursor.fetchall()
    result_list = []
    for result in results:

        pressure_pa = result[2]
        if pressure_pa is None:
            pressure_dict = {
                "pa": None,
                "psi": None,
                "atm": None
            }
        else:
            pressure_dict = {
                "pa": pressure_pa,
                "psi": pressure_pa / 6895,
                "atm": pressure_pa / 101300
            }

        windspeed = result[4]

        if windspeed is None:
            windspeed_dict = {
                "m/s": None,
                "km/h": None,
                "mph": None,
                "kts": None
            }
        else:
            windspeed_dict = {
                "m/s": windspeed,
                "km/h": windspeed * 3.6,
                "mph": windspeed * 2.237,
                "kts": windspeed * 1.944
            }

        temperature = result[6]

        if temperature is None:
            temperature_dict = {
                "kelvin": None,
                "celsius": None,
                "fahrenheit": None
            }
        else:
            temperature_dict = {
                "kelvin": temperature + 273.15,
                "celsius": temperature,
                "fahrenheit": (temperature * (9 / 5)) + 32
            }

        readings_dict = {
            "pressure": pressure_dict,
            "uv_index": result[3],
            "windspeed": windspeed_dict,
            "humidity_perc": result[5],
            "temperature": temperature_dict,
            "is_day": bool(result[7]),
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

        result_list.append(response_dict)


    conn.close()

    return result_list


# structure 1: /country/{country}/town/{town} - GETS LATEST OF A RANDOM STATION AT {country}, {town} (DONE)

# structure 2: /name/{name} - GETS LATEST OF {name} (DONE)

# structure 3: /name/{name}/amount/{amount} - GETS LAST {amount} READINGS (DONE)

# structure 4: /country/{country}/town/{town}/amount/{amount} - GETS LAST {amount} READINGS OF A RANDOM STATION FROM {country} IN {town}

# structure 5: /name/{name}/unix/{unix} - GETS READING OF {name} AT TIME OF {unix}, IF THERE IS NONE, GET THE NEAREST ONE

@app.get("/name/{name}")
async def get_data(name: str):
    sql = """
    SELECT * FROM Readings WHERE (name) = ? ORDER BY timestamp_unix DESC LIMIT 1; 
    """
    response = get_from_db(sql, (name,))
    return JSONResponse(content=response, status_code=200)


@app.get("/country/{country}/town/{town}")
async def get_data(country: str, town: str):
    sql = """
    SELECT * FROM Readings WHERE (country) = ? AND (town) = ?
    """

    station_ids = []

    response = get_from_db(sql, (country, town, ))
    for i in response:
        station_ids.append(i["info"]["station_id"])

    station_ids = list(set(station_ids))

    random_station_id = station_ids[random.randint(0, len(station_ids)-1)]

    sql = """
    SELECT * FROM READINGS WHERE (station_id) = ? ORDER BY timestamp_unix DESC LIMIT 1
    """
    return JSONResponse(content=get_from_db(sql, (random_station_id, )), status_code=200)


@app.get("/name/{name}/amount/{amount}")
async def get_data(name: str, amount: int):

    sql = """
    SELECT * FROM Readings WHERE (name) = ? ORDER BY timestamp_unix DESC LIMIT ?
    """

    return JSONResponse(content=get_from_db(sql, (name, amount)))





