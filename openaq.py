import streamlit as st
import requests
import time
import threading
import tensorflow as tf
import numpy as np
from geopy.geocoders import Nominatim
import geocoder

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

def get_user_city():
    try:
        ip_response = requests.get(GEO_API_URL)
        if ip_response.status_code == 200:
            ip_data = ip_response.json()
            return ip_data.get('city', 'DefaultCity')
    except requests.exceptions.RequestException:
        return 'DefaultCity'

def get_user_city():
    location = geolocator.reverse(get_current_location(), language='en')
    if location:
        city = location.raw.get('city', 'DefaultCity')
        return city
    else:
        return 'DefaultCity'


def continuous_check(city):
    while True:
        weather_response = requests.get(f"http://127.0.0.1:5000/weather?city={city}")
        if weather_response.status_code == 200:
            weather_data = weather_response.json()
            
            lat = weather_data.get("coord", {}).get("lat")
            lon = weather_data.get("coord", {}).get("lon")
            air_quality_response = requests.get(f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}")
            
            if air_quality_response.status_code == 200:
                air_quality_data = air_quality_response.json()["list"][0]["components"]
                
                alerts = check_alerts(weather_data, air_quality_data)
                if alerts:
                    for alert in alerts:
                        print(alert)
            else:
                print("Error fetching air quality data.")
        else:
            print("Error fetching weather data.")
        
        time.sleep(10)
def start_notifications():
    city = get_user_city()
    st.write(f"Weather and air quality notifications are starting for your city: {city}")

    # Start background thread for continuous weather and air quality checking
    if not hasattr(start_notifications, "check_thread"):
        start_notifications.check_thread = threading.Thread(target=continuous_check, args=(city,), daemon=True)
        start_notifications.check_thread.start()

    st.success("Notifications started!")
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
            return data, air_quality_data, alerts
        else:
            st.error(f"Error fetching weather data: {response.status_code}")
            return None, None, ["Failed to retrieve weather data"]
    except requests.exceptions.RequestException as e:
        st.error(f"Error with API request: {e}")
        return None, None, ["Failed to retrieve weather data"]

st.title(" Pollution & Weather Forecast App")
location = get_current_location()
city = get_user_city()

if location:
    lat, lon = location
    weather_data, air_quality_data, alerts = get_weather(lat, lon)
    # st.write(f"Your current city is: {city}")

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
            weather_table = {
                "Temperature (°C)": [weather_data['main']['temp']],
                "Humidity (%)": [weather_data['main']['humidity']],
                "Wind Speed (m/s)": [weather_data['wind']['speed']]
            }
            st.table(weather_table)

            st.subheader("🌫️ Air Quality Information")
            air_quality_table = {
                "Pollutant": list(air_quality_data.keys()),
                "Value (µg/m³)": list(air_quality_data.values())
            }
            st.table(air_quality_table)

            st.subheader("⚠️ Alerts")
            if alerts:
                for alert in alerts:
                    st.warning(alert)
            else:
                st.success("No alerts detected.")

            st.subheader("📊 Predicted Pollution Levels")
            pollution_table = {
                "Pollutant": list(predicted_pollution.keys()),
                "Value (µg/m³)": [data["value"] for data in predicted_pollution.values()],
                "Air Quality": [data["air_quality"] for data in predicted_pollution.values()]
            }
            st.table(pollution_table)

        else:
            st.error("Error fetching data. Try again.")
