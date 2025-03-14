import streamlit as st
import requests
import time
import threading
import tensorflow as tf
import numpy as np
from geopy.geocoders import Nominatim
import geocoder
import matplotlib.pyplot as plt

model = tf.keras.models.load_model("pollution_forecasting_model.keras")
geolocator = Nominatim(user_agent="pollution_forecaster")

WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
AIR_POLLUTION_API_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
WEATHER_API_KEY = "2d0ca46555df760def36fb82d33f32eb"
GEO_API_URL = "http://ip-api.com/json/"

ALERT_THRESHOLDS = {
    "weather": {"temp": 35, "humidity": 80, "wind_speed": 20},
    "air_quality": {'pm10': 50, 'pm2_5': 35, 'co': 5, 'o3': 180, 'no2': 40, 'so2': 75}
}

def get_lat_lon(city_name):
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
        else:
            st.error(f"City '{city_name}' not found.")
            return None, None
    except Exception as e:
        st.error(f"Error getting coordinates for city '{city_name}': {e}")
        return None, None  

def get_current_location():
    try:
        g = geocoder.ip('me')
        return g.latlng  
    except Exception as e:
        st.error(f"Error getting current location: {e}")
        return None  

def map_pollutant_to_air_quality(pollutant, value):
    if value <= 12:
        return "Good"
    elif value <= 35.4:
        return "Moderate"
    elif value <= 55.4:
        return "Unhealthy for Sensitive Groups"
    elif value <= 150.4:
        return "Unhealthy"
    elif value <= 250.4:
        return "Very Unhealthy"
    else:
        return "Hazardous"

def predict_pollution(lat, lon):
    try:
        input_data = np.zeros((1, 1, 10)) 
        input_data[0, 0, 0] = lat
        input_data[0, 0, 1] = lon

        prediction = model.predict(input_data)
        pm25, pm10, co, no2, so2, o3 = map(float, prediction[0])

        return {
            "pm2_5": {"value": pm25, "air_quality": map_pollutant_to_air_quality("pm2_5", pm25)},
            "pm10": {"value": pm10, "air_quality": map_pollutant_to_air_quality("pm10", pm10)},
            "co": {"value": co, "air_quality": map_pollutant_to_air_quality("co", co)},
            "no2": {"value": no2, "air_quality": map_pollutant_to_air_quality("no2", no2)},
            "so2": {"value": so2, "air_quality": map_pollutant_to_air_quality("so2", so2)},
            "o3": {"value": o3, "air_quality": map_pollutant_to_air_quality("o3", o3)}
        }
    except Exception as e:
        st.error(f"Error predicting pollution data: {e}")
        return {}

def get_location_name(lat, lon):
    location = geolocator.reverse((lat, lon), language='en')
    if location:
        return location.address
    else:
        return "Location not found"

def get_weather(lat, lon):
    try:
        weather_url = f"{WEATHER_API_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(weather_url)

        if response.status_code == 200:
            data = response.json()

            air_quality_url = f"{AIR_POLLUTION_API_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
            air_quality_response = requests.get(air_quality_url)
            air_quality_data = air_quality_response.json()["list"][0]["components"] if air_quality_response.status_code == 200 else {}

            alerts = check_alerts(data["main"], air_quality_data)
            if alerts:
                with open("alerts.log", "a") as log_file:
                    for alert in alerts:
                        log_file.write(f"{time.ctime()}: {alert}\n")
                        print(alert) 

            return data, air_quality_data, alerts
        else:
            st.error(f"Error fetching weather data: {response.status_code}")
            return None, None, ["Failed to retrieve weather data"]
    except requests.exceptions.RequestException as e:
        st.error(f"Error with API request: {e}")
        return None, None, ["Failed to retrieve weather data"]

def check_alerts(weather_data, air_quality_data):
    temp = weather_data.get("temp", 0)
    humidity = weather_data.get("humidity", 0)
    wind_speed = weather_data.get("wind_speed", 0)

    alerts = []
    if temp >= ALERT_THRESHOLDS["weather"]["temp"]:
        alerts.append(f"High Temperature Alert: {temp}°C!")
    if humidity >= ALERT_THRESHOLDS["weather"]["humidity"]:
        alerts.append(f"High Humidity Alert: {humidity}%!")
    if wind_speed >= ALERT_THRESHOLDS["weather"]["wind_speed"]:
        alerts.append(f"High Wind Speed Alert: {wind_speed} m/s!")

    for key, threshold in ALERT_THRESHOLDS["air_quality"].items():
        value = air_quality_data.get(key, 0)
        if value >= threshold:
            alerts.append(f"High {key.upper()} Levels: {value} µg/m³!")

    return alerts

st.title("Pollution & Weather Forecast App")
location = get_current_location()

if location:
    lat, lon = location
    city = get_location_name(lat, lon)
    weather_data, air_quality_data, alerts = get_weather(lat, lon)
    st.write(f"Your current city is: {city}")

    if weather_data:
        st.subheader("⚠️ Alerts")
        if alerts:
            for alert in alerts:
                st.warning(alert)  
        else:
            st.success("No alerts detected.")
    else:
        st.error("Error fetching weather or air quality data.")
else:
    st.error("Unable to retrieve your location.")

city = city.split(",")
city = city[3]
city = st.text_input("Enter city name (leave empty to use current location):", f"{city}")
lat, lon = None, None

if city:
    lat, lon = get_lat_lon(city)
else:
    lat, lon = get_current_location()

if st.button("Get Weather & Pollution Data"):
    if lat is not None and lon is not None:
        weather_data, air_quality_data, alerts = get_weather(lat, lon)
        predicted_pollution = predict_pollution(lat, lon)

        if weather_data:
            st.subheader("🌦️ Weather Information")
            st.write(f"Temperature: {weather_data['main']['temp']} °C")
            st.write(f"Humidity: {weather_data['main']['humidity']} %")
            st.write(f"Wind Speed: {weather_data['wind']['speed']} m/s")

            st.subheader("🌫️ Air Quality Information")
            pollutants = list(air_quality_data.keys())
            values = list(air_quality_data.values())

            st.subheader("Air Quality Graph")
            fig, ax = plt.subplots()
            ax.bar(pollutants, values, color='skyblue')
            ax.set_xlabel('Pollutants')
            ax.set_ylabel('Concentration (µg/m³)')
            ax.set_title('Air Quality Levels')
            st.pyplot(fig)

            st.subheader("⚠️ Alerts")
            if alerts:
                for alert in alerts:
                    st.warning(alert)
            else:
                st.success("No alerts detected.")

            st.subheader("📊 Predicted Pollution Levels")
            pollution_pollutants = list(predicted_pollution.keys())
            pollution_values = [data["value"] for data in predicted_pollution.values()]

            st.subheader("Predicted Pollution Graph")
            fig2, ax2 = plt.subplots()
            ax2.bar(pollution_pollutants, pollution_values, color='salmon')
            ax2.set_xlabel('Pollutants')
            ax2.set_ylabel('Concentration (µg/m³)')
            ax2.set_title('Predicted Pollution Levels')
            st.pyplot(fig2)

        else:
            st.error("Error fetching data. Try again.")
