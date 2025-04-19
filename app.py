import streamlit as st
from geopy.distance import geodesic
from PIL import Image, ExifTags
import folium
from streamlit_folium import st_folium
import pandas as pd
import os
from datetime import datetime
from geopy.geocoders import Nominatim

# Constants
PROJECT_LOCATIONS = {
    "project_id_123": (26.8467, 80.9462),
    "project_id_456": (28.6139, 77.2090),
    "project_id_789": (23.367311, 85.325555),
}

# Initialize Geolocator
geolocator = Nominatim(user_agent="geo_checker")

# Helper Functions
def get_exif_location(img):
    try:
        exif_data = img._getexif()
        if not exif_data:
            return None
        gps_info = {}
        for tag, val in exif_data.items():
            decoded = ExifTags.TAGS.get(tag)
            if decoded == "GPSInfo":
                for t in val:
                    sub_decoded = ExifTags.GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = val[t]

        def convert_to_deg(value):
            d, m, s = value
            return d[0]/d[1] + (m[0]/m[1])/60 + (s[0]/s[1])/3600

        lat = convert_to_deg(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] != 'N':
            lat = -lat
        lon = convert_to_deg(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] != 'E':
            lon = -lon
        return (lat, lon)
    except:
        return None

def fake_ai_check(filename):
    keywords = ['construction', 'site', 'work', 'cement', 'build']
    return any(k in filename.lower() for k in keywords)

def log_data(data, log_file="upload_logs.csv"):
    df = pd.DataFrame([data])
    if os.path.exists(log_file):
        df.to_csv(log_file, mode='a', header=False, index=False)
    else:
        df.to_csv(log_file, index=False)

def get_risk_level(distance, ai_pass):
    if not ai_pass or distance > 1.5:
        return "High", "🔴"
    elif distance > 1.0:
        return "Medium", "🟠"
    return "Low", "🟢"

# Streamlit App
st.set_page_config(page_title="Geo-tag AI", layout="centered")
st.title("Jan Darpan Geo-tag AI")

project_id = st.selectbox("Select Project ID", list(PROJECT_LOCATIONS.keys()))
project_coords = PROJECT_LOCATIONS[project_id]
uploaded_file = st.file_uploader("Upload Site Image", type=["jpg", "jpeg", "png"])

manual_coords = None
if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Uploaded Image", use_column_width=True)

    exif_coords = get_exif_location(img)
    if not exif_coords:
        st.warning("No EXIF GPS found. Enter manually.")
        lat = st.number_input("Latitude", format="%.6f")
        lon = st.number_input("Longitude", format="%.6f")
        if lat and lon:
            manual_coords = (lat, lon)

    coords_to_check = exif_coords or manual_coords

    if coords_to_check:
        distance_km = geodesic(project_coords, coords_to_check).km
        is_within = distance_km <= 1.0
        st.write(f"📏 Distance from site: `{distance_km:.3f} km`")
        st.markdown(f"**Location Check:** {'✅ Within Range' if is_within else '🚨 Outside 1km Radius'}")

        ai_pass = fake_ai_check(uploaded_file.name)
        st.write(f"**Image Filename Check:** {'✅ Looks relevant' if ai_pass else '⚠️ Unclear if construction-related'}")

        # Risk level feedback
        risk, emoji = get_risk_level(distance_km, ai_pass)
        st.write(f"**Corruption Risk Meter:** {emoji} {risk}")

        # Reverse Geocoding
        location_name = geolocator.reverse(coords_to_check, language='en')
        st.write(f"📍 Location Name: {location_name.address if location_name else 'Not found'}")

        # Show map
        m = folium.Map(location=project_coords, zoom_start=14)
        folium.Marker(project_coords, tooltip="Project Site", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords_to_check, tooltip="Upload Location", icon=folium.Icon(color="red")).add_to(m)
        folium.Circle(project_coords, radius=1000, color="blue", fill=True, fill_opacity=0.1).add_to(m)
        st_folium(m, width=700)

        log_data({
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "latitude": coords_to_check[0],
            "longitude": coords_to_check[1],
            "distance_km": round(distance_km, 3),
            "location_valid": is_within,
            "image_valid": ai_pass,
            "risk_level": risk,
            "status": "Flagged" if not is_within or not ai_pass else "Valid"
        })

if st.checkbox(" View Upload History"):
    if os.path.exists("upload_logs.csv"):
        logs = pd.read_csv("upload_logs.csv")
        st.dataframe(logs)
    else:
        st.info("No uploads logged yet.")
