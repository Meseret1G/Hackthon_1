from flask import Flask, jsonify, request, render_template
import requests
import time
import threading
import tensorflow as tf
import numpy as np
from geopy.geocoders import Nominatim

app = Flask(__name__)

WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
AIR_POLLUTION_API_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
WEATHER_API_KEY = "2d0ca46555df760def36fb82d33f32eb" 
GEO_API_URL = "http://ip-api.com/json/"
model = tf.keras.models.load_model("pollution_forecasting_model.keras")
geolocator = Nominatim(user_agent="pollution_forecaster")

ALERT_THRESHOLDS = {
    "weather": {
        "temp": 35,  
        "humidity": 80, 
        "wind_speed": 20, 
    },
    "air_quality": {
        'pm10': 50,
        'pm2_5': 35,
        'co': 5,
        'o3': 180,
        'no2': 40,
        'so2': 75
    }
}

def get_lat_lon(city_name):
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None  

def map_pollutant_to_air_quality(pollutant, value):
    if pollutant == "pm2_5" or pollutant == "pm10" or pollutant == "co"or pollutant == "no2" or pollutant == "o3" or pollutant == "so2":
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
    return "Unknown"

def predict_pollution(city_name):
    lat, lon = get_lat_lon(city_name)
    
    if lat is None or lon is None:
        return {"error": "City not found"}
    
    input_data = np.zeros((1, 1, 10)) 
    input_data[0, 0, 0] = lat
    input_data[0, 0, 1] = lon

    prediction = model.predict(input_data)
    
    print("Prediction output shape:", prediction.shape) 
    print("Prediction output:", prediction) 
    
    pm25 = float(prediction[0][0])  
    pm10 = float(prediction[0][1])  
    co = float(prediction[0][2])    
    no2 = float(prediction[0][3])   
    so2 = float(prediction[0][4])   
    o3 = float(prediction[0][5])    
    
    air_quality_pm25 = map_pollutant_to_air_quality("pm2_5", pm25)
    air_quality_pm10 = map_pollutant_to_air_quality("pm10", pm10)
    air_quality_co = map_pollutant_to_air_quality("co", co)
    air_quality_no2 = map_pollutant_to_air_quality("no2", no2)
    air_quality_so2 = map_pollutant_to_air_quality("so2", so2)
    air_quality_o3 = map_pollutant_to_air_quality("o3", o3)
    
    return {
        "city": city_name,
        "pm2_5": {"value": pm25, "air_quality": air_quality_pm25},
        "pm10": {"value": pm10, "air_quality": air_quality_pm10},
        "co": {"value": co, "air_quality": air_quality_co},
        "no2": {"value": no2, "air_quality": air_quality_no2},
        "so2": {"value": so2, "air_quality": air_quality_so2},
        "o3": {"value": o3, "air_quality": air_quality_o3}
    }


@app.route("/predict", methods=["GET"])
def predict():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "Please provide a city name"}), 400

    result = predict_pollution(city)
    return jsonify(result)

def check_alerts(weather_data, air_quality_data):
    temp = weather_data.get("main", {}).get("temp", 0)
    humidity = weather_data.get("main", {}).get("humidity", 0)
    wind_speed = weather_data.get("wind", {}).get("speed", 0)

    alerts = []
    if temp >= ALERT_THRESHOLDS["weather"]["temp"]:
        alerts.append(f" High Temperature Alert: {temp}°C!")
    if humidity >= ALERT_THRESHOLDS["weather"]["humidity"]:
        alerts.append(f" High Humidity Alert: {humidity}%!")
    if wind_speed >= ALERT_THRESHOLDS["weather"]["wind_speed"]:
        alerts.append(f" High Wind Speed Alert: {wind_speed} m/s!")

    for key, threshold in ALERT_THRESHOLDS["air_quality"].items():
            value = air_quality_data.get(key, 0)
            if value >= threshold:
                alerts.append(f" High {key.upper()} Levels: {value} µg/m³!")

    return alerts

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/forecast', methods=['GET'])
def forecast_pollution():
    city = request.args.get('city')
    if not city:
        location_data = requests.get(GEO_API_URL).json()
        city = location_data.get("city", "Unknown")
    
    weather_url = f"{WEATHER_API_URL}?q={city}&appid={WEATHER_API_KEY}&units=metric"
    weather_response = requests.get(weather_url)
    if weather_response.status_code != 200:
        return jsonify({'error': 'Failed to retrieve weather data'}), 500
    weather_data = weather_response.json()["main"]
    
    lat, lon = weather_response.json()["coord"]["lat"], weather_response.json()["coord"]["lon"]
    air_quality_url = f"{AIR_POLLUTION_API_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
    air_quality_response = requests.get(air_quality_url)
    if air_quality_response.status_code != 200:
        return jsonify({'error': 'Failed to retrieve air quality data'}), 500
    air_quality_data = air_quality_response.json()["list"][0]["components"]
    
    input_data = np.array([
        [weather_data["temp"], weather_data["humidity"], air_quality_data.get("pm10", 0), air_quality_data.get("pm2_5", 0)]
    ])
    
    predicted_pollution = model.predict(input_data)[0]
    alerts = check_alerts(weather_data, air_quality_data)
    
    return jsonify({
        'city': city,
        'weather': weather_data,
        'air_quality': air_quality_data,
        'predicted_pollution': predicted_pollution.tolist(),
        'alerts': alerts
    })
@app.route('/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city')
    
    if not city:
        location_data = requests.get(GEO_API_URL).json()
        city = location_data.get("city", location_data["city"])
        
    url = f"{WEATHER_API_URL}?q={city}&appid={WEATHER_API_KEY}&units=metric"
    weather_response = requests.get(url)

    if weather_response.status_code == 200:
        weather_data = weather_response.json()
        lat, lon = weather_data['coord']['lat'], weather_data['coord']['lon']

        air_auality_url = f'{AIR_POLLUTION_API_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}'
        air_quality_response = requests.get(air_auality_url)
        
        if air_quality_response.status_code == 200:
            air_quality_data = air_quality_response.json()["list"][0]["components"]
        else:
            air_quality_data = {}
        
        alerts = check_alerts(weather_data, air_quality_data)

        if alerts:
            with open("alerts.log", "a") as log_file:
                for alert in alerts:
                    log_file.write(f"{time.ctime()}: {alert}\n")
                    print(alert) 

        return jsonify({
            'weather': weather_data,
            'air_quality': air_quality_data,
            'alerts': alerts
        })
    else:
        return jsonify({'error': 'Failed to retrieve weather data'}), 500
    
    
def get_user_city():
    ip_response = requests.get(GEO_API_URL)
    if ip_response.status_code == 200:
        ip_data = ip_response.json()
        return ip_data.get('city', 'DefaultCity') 
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

@app.route('/set_notifications', methods=['POST'])
def set_notifications():
    city = get_user_city()

    if not hasattr(set_notifications, "check_thread"):
        set_notifications.check_thread = threading.Thread(target=continuous_check, args=(city,), daemon=True)
        set_notifications.check_thread.start()
    
    return jsonify({"message": "Weather notifications for your location started!"}), 200

if __name__ == '__main__':
    city = get_user_city() 
    threading.Thread(target=continuous_check, daemon=True).start()
    app.run(debug=True)
