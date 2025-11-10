import json
import random
import uuid

import os
from dotenv import load_dotenv, dotenv_values

import mariadb
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from pydantic import BaseModel
from fastapi.responses import JSONResponse, orjson

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler

debug = False

load_dotenv()

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
    windspeed_ms: Optional[float] = None
    humidity_perc: Optional[int] = None
    temperature_c: Optional[float] = None
    is_day: Optional[bool] = None
    air_quality: Optional[str] = None
    is_raining: Optional[bool] = None


app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"\n--- VALIDATION ERROR ---")
    print(f"URL: {request.url}")
    print(f"Body: {await request.body()}")
    print(f"Errors: {exc.errors()}")
    print(f"------------------------\n")

    return await request_validation_exception_handler(request, exc)

@app.get("/", include_in_schema=False)
async def redirect(request: Request):
    # Check the Host header to determine the domain
    if request.headers.get("host") == "api.nelsons.lv":
        response = RedirectResponse(url='/docs')
        return response

@app.post("/upload/",
          summary="Upload readings of weather station to the API",
          description="Takes in data in json format. Token is mandatory for verifying whether the weather station is legitimate")
async def upload_to_db(readings: Readings):
    readings_dict = {}

    for i in readings:
        reading_name = i[0]
        reading = i[1]
        readings_dict[reading_name] = reading
    readings = readings_dict

    errors = []

    try:
        conn = mariadb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host="localhost",
            port=3306,
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()

        timestamp_unix = int(time.time())

        # Check if token is valid
        cursor.execute("SELECT * FROM Stations WHERE (`uuid`) = ?", (readings["token"],))
        result = cursor.fetchone()

        if result is None:
            raise HTTPException(status_code=400, detail={"message": "Bad request!"})

        if readings[is_raining_name] not in (1, 0, None):
            errors.append(f"Error: {is_raining_name} can only be 1 (true), 0 (false), or null, got {readings[is_raining_name]} instead!")
            readings[is_raining_name] = None

        if readings[pressure_name] is not None and not (87_000 <= readings[pressure_name] <= 108_500):
            errors.append(f"Error: {pressure_name} must be within the range of 87,000 and 108,500 pascals, got {readings[pressure_name]} instead!")
            readings[pressure_name] = None

        if readings[uv_index_name] is not None and not (0 <= readings[uv_index_name] <= 25):
            errors.append(f"Error: {uv_index_name} must be within the range of 0 and 25, got {readings[uv_index_name]} instead!")
            readings[uv_index_name] = None

        if readings[humidity_name] is not None and not (0 <= readings[humidity_name] <= 100):
            errors.append(f"Error: {humidity_name} must be within the range of 0 and 100 percent, got {readings[humidity_name]} instead!")
            readings[humidity_name] = None

        if readings[temperature_name] is not None and not (-90 <= readings[temperature_name] <= 60):
            errors.append(f"Error: {temperature_name} must be within the range of -90 and 60 degrees celsius, got {readings[temperature_name]} instead!")
            readings[temperature_name] = None

        if readings[is_day_name] not in (1, 0, None):
            errors.append(f"Error: {is_day_name} can only be 1 (true), 0 (false), or null, got {readings[is_day_name]} instead!")
            readings[is_day_name] = None

        if readings[windspeed_name] is not None and not (0 <= readings[windspeed_name] <= 115):
            errors.append(f"Error: {windspeed_name} can only be within the range of 0 and 115 meters per second, got {readings[windspeed_name]} instead!")
            readings[windspeed_name] = None

        if readings[air_quality_name] is not None and readings[air_quality_name].lower() not in ("good", "moderate", "bad"):
            errors.append(
                f"Error: {air_quality_name} only accepts values 'good', 'moderate', and 'bad'. Qualitative data coming at a later date!, got {readings[air_quality_name]} instead!")
            readings[air_quality_name] = None

        station_id = result[0]
        country = result[1]
        town = result[2]
        name = result[3]

        sql = f"""INSERT INTO Readings
                 (`station_id`, `{pressure_name}`, `{uv_index_name}`, `{windspeed_name}`, `{humidity_name}`, `{temperature_name}`, `{is_day_name}`, `{air_quality_name}`, `{is_raining_name}`, `country`, `town`, `name`, `timestamp_unix`)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

        cursor.execute(sql, (
            station_id,
            readings[pressure_name],
            readings[uv_index_name],
            readings[windspeed_name],
            readings[humidity_name],
            readings[temperature_name],
            readings[is_day_name],
            readings[air_quality_name],
            readings[is_raining_name],
            country,
            town,
            name,
            timestamp_unix
        ))

        conn.commit()

    except mariadb.Error as e:
        print(f"DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error.")
    finally:
        if conn:
            conn.close()

    returnable = {
        "status": "Uploaded successfully!"
    }

    if errors:
        returnable["status"] += " However, there were some issues"
        returnable["errors"] = errors

    return JSONResponse(content=returnable, status_code=201)


def get_from_readings(query: str, values: tuple):
    try:
        conn = mariadb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host="localhost",
            port=3306,
            database=os.getenv("DB_NAME")
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    cursor.execute(query, values)
    results = cursor.fetchall()
    conn.close()
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
                "pa": round(pressure_pa, 2),
                "psi": round(pressure_pa / 6895, 2),
                "atm": round(pressure_pa / 101300, 2)
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
                "m_s": round(windspeed, 2),
                "km_h": round(windspeed * 3.6, 2),
                "mph": round(windspeed * 2.237, 2),
                "kts": round(windspeed * 1.944, 2)
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
                "kelvin": round(temperature + 273.15, 2),
                "celsius": round(temperature, 2),
                "fahrenheit": round((temperature * (9 / 5)) + 32, 2)
            }

        readings_dict = {
            "pressure": pressure_dict,
            "uv_index": result[3],
            "windspeed": windspeed_dict,
            "humidity_perc": result[5],
            "temperature": temperature_dict,
            "is_day": bool(result[7]) if result[7] is not None else None,
            "air_quality": result[8],
            "is_raining": bool(result[9]) if result[9] is not None else None
        }

        timestamp_dict = {
            "unix": result[13],
            "iso8601": datetime.fromtimestamp(result[13], tz=timezone.utc).isoformat()
        }
        info_dict = {
            "reading_id": result[0],
            "station_id": result[1],
            "timestamp": timestamp_dict,
            "country": result[10],
            "town": result[11],
            "name": result[12]
        }

        response_dict = {
            "info": info_dict,
            "readings": readings_dict
        }

        result_list.append(response_dict)

    return result_list


# structure 1: /country/{country}/town/{town} - GETS LATEST OF A RANDOM STATION AT {country}, {town} (DONE)

# structure 2: /name/{name} - GETS LATEST OF {name} (DONE)

# structure 3: /name/{name}/amount/{amount} - GETS LAST {amount} READINGS (DONE)

# structure 4: /country/{country}/town/{town}/amount/{amount} - GETS LAST {amount} READINGS OF A RANDOM STATION FROM {country} IN {town}

# structure 5: /name/{name}/unix/{unix} - GETS READING OF {name} AT TIME OF {unix}, IF THERE IS NONE, GET THE NEAREST ONE

@app.get("/name/{name}", summary="Get the latest reading of specified weather station")
async def get_data(name: str):
    sql = """
    SELECT * FROM Readings WHERE (name) = ? ORDER BY timestamp_unix DESC LIMIT 1; 
    """
    response = get_from_readings(sql, (name,))
    return JSONResponse(content=response, status_code=200)


@app.get("/country/{country}/town/{town}",
         summary="Get the latest reading of a random weather station in the specified country and town")
async def get_data(country: str, town: str):
    sql = """
    SELECT * FROM Readings WHERE (country) = ? AND (town) = ?
    """

    station_ids = []

    response = get_from_readings(sql, (country, town,))
    for i in response:
        station_ids.append(i["info"]["station_id"])

    station_ids = list(set(station_ids))

    random_station_id = station_ids[random.randint(0, len(station_ids) - 1)]

    sql = """
    SELECT * FROM Readings WHERE (station_id) = ? ORDER BY timestamp_unix DESC LIMIT 1
    """
    return JSONResponse(content=get_from_readings(sql, (random_station_id,)), status_code=200)


@app.get("/name/{name}/amount/{amount}", summary="Get last {amount} of readings from the specified weather station")
async def get_data(name: str, amount: int):
    if amount > 2500:
        amount = 2500

    sql = """
    SELECT * FROM Readings WHERE (name) = ? ORDER BY timestamp_unix DESC LIMIT ?
    """

    return JSONResponse(content=get_from_readings(sql, (name, amount)))


@app.get("/all-stations", summary="Get all of the stations currently being hosted")
async def get_data():
    sql = """
    SELECT * FROM Stations;
    """

    try:
        conn = mariadb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host="localhost",
            port=3306,
            database=os.getenv("DB_NAME")
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        return JSONResponse(status_code=500)
    returnable = []
    cursor = conn.cursor()
    cursor.execute(sql)
    results = cursor.fetchall()
    for result in results:
        station_dict = {
            "country": result[1],
            "city": result[2],
            "name": result[3]
        }
        returnable.append(station_dict)

    return JSONResponse(content=returnable, status_code=200)
