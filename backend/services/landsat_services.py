import requests
from skyfield.api import EarthSatellite, load, Topos
from datetime import datetime, timedelta, timezone
import math
import threading
from email.mime.text import MIMEText
from plyer import notification
import os
import smtplib

LANDSAT_9_CATALOG_NUM = 49260
LANDSAT_8_CATALOG_NUM = 39084
COVERAGE_OF_EARTH_IN_DAYS = 16
EMAIL_SENDER = "landsat.notification@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = "flameisntlame@gmail.com"

# Function to get GP data (TLE) from CelesTrak for a given catalog number
def get_tle_from_celestrak(catalog_number):
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_number}&FORMAT=TLE"
    response = requests.get(url)
    
    if response.status_code == 200:
        tle_data = response.text.strip().splitlines()
        if len(tle_data) >= 3:
            return tle_data[1], tle_data[2]
        else:
            raise Exception("Incomplete TLE data received from CelesTrak")
    else:
        raise Exception(f"Failed to retrieve TLE data. Status Code: {response.status_code}")

# Existing calculate_next_overpass function
def calculate_next_overpass(latitude, longitude, landsat_number, start_time = datetime.now(tz=timezone.utc), end_time = -1):
    if (end_time == -1):
        end_time = start_time + timedelta(days=COVERAGE_OF_EARTH_IN_DAYS)
    altitude_degrees = 90 - math.degrees(math.atan((180 / 2) / 705))
    
    try:
        if landsat_number == 8:
            catalog_number = LANDSAT_8_CATALOG_NUM
        elif landsat_number == 9:
            catalog_number = LANDSAT_9_CATALOG_NUM
        else:
            raise ValueError("Invalid Landsat number. Please select 8 or 9.")

        tle_line_1, tle_line_2 = get_tle_from_celestrak(catalog_number)
        ts = load.timescale()
        satellite = EarthSatellite(tle_line_1, tle_line_2, f"Landsat {landsat_number}", ts)
        observer = Topos(latitude_degrees=latitude, longitude_degrees=longitude)
        t0 = start_time
        t1 = end_time
        t, is_visible = satellite.find_events(observer, t0, t1, altitude_degrees=altitude_degrees)

        for ti, event_type in zip(t, is_visible):
            if event_type == 0:  # Satellite rising
                return ti.utc_datetime()

        return None

    except Exception as e:
        raise RuntimeError(f"Error calculating overpass: {e}")

# Function to send a notification
def send_notification(landsat_number, overpass_time, notification_method):
    local_overpass_time_str = overpass_time.astimezone().strftime('%Y-%m-%d %I:%M %p')
    
    if notification_method == "desktop" or notification_method == "both":
        notification.notify(
            title=f"Landsat {landsat_number} Overpass Alert",
            message=f"Landsat {landsat_number} will pass over at {local_overpass_time_str} (local time).",
            timeout=10
        )
    
    if notification_method == "email" or notification_method == "both":
        try:
            subject = f"Landsat {landsat_number} Overpass Alert"
            body = f"Landsat {landsat_number} will pass over at {local_overpass_time_str} (local time)."
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
            print("Email notification sent successfully.")
        except Exception as e:
            print(f"Failed to send email notification: {e}")

# Function to set up a notification for the next overpass
def setup_notification(latitude, longitude, landsat_number, notification_lead_time_minutes, notification_method):
    try:
        next_overpass = calculate_next_overpass(latitude, longitude, landsat_number)
        if next_overpass:
            notification_time = next_overpass - timedelta(minutes=notification_lead_time_minutes)
            current_time = datetime.now(tz=timezone.utc)
            time_to_wait = (notification_time - current_time).total_seconds()

            if time_to_wait > 0:
                threading.Timer(time_to_wait, send_notification, [landsat_number, next_overpass, notification_method]).start()
                return {
                    'success': True,
                    'message': f"Notification set for Landsat {landsat_number} overpass at {next_overpass} UTC, notification will be sent {notification_lead_time_minutes} minutes before via {notification_method}."
                }
            else:
                return {
                    'success': False,
                    'message': "The next overpass is too soon to set up a notification."
                }
        else:
            return {
                'success': False,
                'message': "Unable to determine the next overpass time."
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
