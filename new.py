import streamlit as st
from geopy.distance import geodesic
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import folium
from streamlit_folium import st_folium
from transformers import CLIPProcessor, CLIPModel
import torch
import numpy as np

# === Extract EXIF GPS ===
def get_exif_location(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None
        gps_info = {}
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]
        def convert_to_degrees(value):
            d, m, s = value
            return d[0]/d[1] + (m[0]/m[1])/60 + (s[0]/s[1])/3600
        lat = convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] != 'N':
            lat = -lat
        lon = convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] != 'E':
            lon = -lon
        return (lat, lon)
    except:
        return None

# === Image Classification using CLIP ===
def classify_image_with_clip(image):
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    labels = [
        "construction site",
        "road construction",
        "pipeline installation",
        "open field",
        "indoor room",
        "group of people",
        "text document",
        "selfie",
        "screenshot or fake photo",
        "school building",
        "government office"
    ]

    inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
    outputs = model(**inputs)
    probs = outputs.logits_per_image.softmax(dim=1).detach().numpy()[0]
    
    sorted_indices = np.argsort(probs)[::-1]
    top_matches = [(labels[i], probs[i]) for i in sorted_indices[:3]]
    top_label, top_prob = top_matches[0]
    
    return top_label, top_prob, top_matches

# === Streamlit App ===
st.set_page_config(page_title="Jan Darpan Geo-AI", layout="centered")
st.title("📍 Jan Darpan: Geo-tag + AI Image Verifier")

PROJECT_LOCATIONS = {
    "project_id_123": (26.8467, 80.9462),
    "project_id_456": (28.6139, 77.2090),
}

project_id = st.selectbox("Select Project ID", list(PROJECT_LOCATIONS.keys()))
project_coords = PROJECT_LOCATIONS[project_id]
uploaded_file = st.file_uploader("Upload Image (with EXIF or Manual Entry)", type=["jpg", "jpeg", "png"])

manual_coords = None
if uploaded_file:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Uploaded Image", use_column_width=True)

    # === Location Check ===
    exif_coords = get_exif_location(image)
    if not exif_coords:
        st.warning("⚠️ No EXIF GPS data found. Please enter location manually.")
        lat = st.number_input("Latitude", format="%.6f")
        lon = st.number_input("Longitude", format="%.6f")
        if lat and lon:
            manual_coords = (lat, lon)

    coords_to_check = exif_coords if exif_coords else manual_coords

    if coords_to_check:
        distance_km = geodesic(project_coords, coords_to_check).km
        is_within = distance_km <= 1.0
        st.markdown("### 📏 Location Check")
        st.write(f"Distance from project site: **{distance_km:.2f} km**")
        if is_within:
            st.success("✅ Location is valid (within 1 km radius).")
        else:
            st.error("🚨 Location is outside valid range!")

        m = folium.Map(location=project_coords, zoom_start=13)
        folium.Marker(project_coords, tooltip="Project Site", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords_to_check, tooltip="Upload Location", icon=folium.Icon(color="red")).add_to(m)
        st_folium(m, width=700)

    # === AI Content Classification ===
    st.markdown("### 🧠 AI Content Check")
    with st.spinner("Analyzing image content with AI..."):
        top_label, top_prob, top_matches = classify_image_with_clip(image)

    st.write(f"🔍 **Best Match:** {top_label} ({top_prob:.2%})")
    if top_label in ["screenshot or fake photo", "indoor room", "selfie", "text document"]:
        st.error("🚨 Suspicious content detected! This image may not be valid.")
    else:
        st.success("✅ Image appears to represent a valid project site.")

    st.markdown("### 🧾 Top 3 Predictions")
    for label, prob in top_matches:
        st.write(f"• **{label}** — {prob:.2%}")
