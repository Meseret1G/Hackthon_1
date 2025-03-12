from flask import Flask, jsonify, request, render_template
import requests
import time
import threading

app = Flask(__name__)

WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_API_KEY = "2d0ca46555df760def36fb82d33f32eb" 
GEO_API_URL = "http://ip-api.com/json/"

ALERT_THRESHOLD = {
    "temp": 35,  
    "humidity":   50, 
    "wind_speed": 15, 
}

def check_alerts(weather_data):
    temp = weather_data.get("main", {}).get("temp", 0)
    humidity = weather_data.get("main", {}).get("humidity", 0)
    wind_speed = weather_data.get("wind", {}).get("speed", 0)

    alerts = []
    if temp >= ALERT_THRESHOLD["temp"]:
        alerts.append(f" High Temperature Alert: {temp}°C!")
    if humidity >= ALERT_THRESHOLD["humidity"]:
        alerts.append(f" High Humidity Alert: {humidity}%!")
    if wind_speed >= ALERT_THRESHOLD["wind_speed"]:
        alerts.append(f" High Wind Speed Alert: {wind_speed} m/s!")

    return alerts

@app.route('/')
def home():
    return render_template('index.html')

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

        alerts = check_alerts(weather_data)

        if alerts:
            with open("alerts.log", "a") as log_file:
                for alert in alerts:
                    log_file.write(f"{time.ctime()}: {alert}\n")
                    print(alert) 

        return jsonify({
            'weather': weather_data,
            'alerts': alerts
        })
    else:
        return jsonify({'error': 'Failed to retrieve weather data'}), 500
def get_user_city():
    """Get the user's city based on their IP address."""
    ip_response = requests.get(GEO_API_URL)
    if ip_response.status_code == 200:
        ip_data = ip_response.json()
        return ip_data.get('city', 'DefaultCity') 
    return 'DefaultCity'

def continuous_check(city):
    while True:
        response = requests.get(f"http://127.0.0.1:5000/weather?city={city}")
        print("Checked Weather:", response.json())  
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
