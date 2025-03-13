import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify
from geopy.geocoders import Nominatim

model = tf.keras.models.load_model("pollution_forecasting_model.keras")

openaq = Flask(__name__)

geolocator = Nominatim(user_agent="pollution_forecaster")

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


@openaq.route("/predict", methods=["GET"])
def predict():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "Please provide a city name"}), 400

    result = predict_pollution(city)
    return jsonify(result)

if __name__ == "__main__":
    openaq.run(debug=True)