from datetime import datetime, timezone, timedelta
import io
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
import streamlit as st
from streamlit_geolocation import streamlit_geolocation

# --- 1. PAGE SETUP ---
st.set_page_config(
    page_title="OHE ATD Smart Tool GIS", page_icon="⚡", layout="centered"
)

st.markdown(
    """
    <style>
    .stApp { background-color: #050a0f; color: white; }
    .area-box { 
        padding: 15px; 
        background-color: #1c2128; 
        border: 2px solid #00d4ff; 
        border-radius: 12px; 
        text-align: center;
        margin: 15px 0px;
    }
    .area-label { color: #00d4ff; font-size: 14px; margin-bottom: 2px; font-weight: bold; }
    .area-text { font-size: 18px; font-weight: bold; color: #ffffff; }
    .length-display {
        font-size: 24px !important;
        font-weight: bold;
        color: #00ff41;
        padding: 12px;
        background: #1c2128;
        border-radius: 8px;
        border-left: 8px solid #00ff41;
        margin: 10px 0px;
    }
    .stButton>button {
        background-color: #00d4ff !important;
        color: black !important;
        font-weight: bold !important;
        width: 100% !important;
        height: 3.5em !important;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 2. DATA LOADING (Nayi Sheet ID ke sath) ---
SHEET_ID = "1VYubXUbniIrCNZlybPQD8lC71SS2wBYlR-kF_EtD5IY"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"


@st.cache_data
def load_sheet_data():
  try:
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip()
    return df
  except:
    return None


# --- 3. GIS NEAREST STRUCTURE FINDER (Haversine Formula) ---
def get_nearest_structure_by_gps(current_lat, current_lon, df):
  if (
      df is None
      or "Latitude" not in df.columns
      or "Longitude" not in df.columns
  ):
    return None, None, None

  # Convert latitude and longitude to radians
  lat1, lon1 = np.radians(current_lat), np.radians(current_lon)
  lat2, lon2 = np.radians(df["Latitude"]), np.radians(df["Longitude"])

  # Haversine formula
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = (
      np.sin(dlat / 2.0) ** 2
      + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
  )
  c = 2 * np.arcsin(np.sqrt(a))
  distance_meters = 6367 * c * 1000  # Radius of earth in meters

  min_idx = distance_meters.idxmin()
  nearest_dist = distance_meters[min_idx]

  # 150 meter ke daayre mein hone par hi auto-select hoga
  if nearest_dist <= 150:
    struct_no = df.loc[min_idx, "Structure_No"]
    tension_len = df.loc[min_idx, "Tension_Length"]
    return struct_no, tension_len, round(nearest_dist, 1)

  return None, None, None


# --- 4. ADVANCED WEATHER ENGINE ---
def get_weather_by_coords(lat, lon):
  try:
    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    w_res = requests.get(w_url, timeout=5).json()
    return round(float(w_res["current_weather"]["temperature"]), 1)
  except:
    return 35.0


def get_manual_city_data(city_name):
  try:
    geo_url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
    res = requests.get(
        geo_url, headers={"User-Agent": "RailwayTool"}, timeout=5
    ).json()
    if res:
      lat, lon = res[0]["lat"], res[0]["lon"]
      temp = get_weather_by_coords(lat, lon)
      return temp, res[0]["display_name"]
    return 35.0, "City Not Found"
  except:
    return 35.0, "Network Error"


# --- 5. UI INITIALIZATION ---
st.markdown(
    "<h2 style='text-align: center; color: #00d4ff;'>OHE ATD Smart Tool"
    " (GIS)</h2>",
    unsafe_allow_html=True,
)

if "temp_val" not in st.session_state:
  st.session_state.temp_val = 35.0
if "area_name" not in st.session_state:
  st.session_state.area_name = "GPS Not Active"
if "auto_struct" not in st.session_state:
  st.session_state.auto_struct = None
if "auto_length" not in st.session_state:
  st.session_state.auto_length = 750.0

df = load_sheet_data()

# --- 6. LOCATION & STRUCTURE SELECTION MODE ---
manual_loc = st.checkbox("✍️ Enter Location & Structure Manually")

if manual_loc:
  city_input = st.text_input("Enter City Name", value="Rajkot")
  if st.button("🔍 FETCH TEMP FOR THIS CITY"):
    with st.spinner("Fetching data..."):
      t, a = get_manual_city_data(city_input)
      st.session_state.temp_val = t
      st.session_state.area_name = a

  if df is not None:
    struct_list = df["Structure_No"].dropna().unique().tolist()
    selected_struct = st.selectbox(
        "📍 Select Structure No Manually", ["Manual Entry"] + struct_list
    )
    if selected_struct != "Manual Entry":
      L = float(
          df[df["Structure_No"] == selected_struct]["Tension_Length"].values[0]
      )
      st.markdown(
          f"<div class='length-display'>Tension Length (L): {L} m</div>",
          unsafe_allow_html=True,
      )
    else:
      L = st.number_input("Enter Tension Length (L) manually", value=750.0)
  else:
    L = st.number_input("Enter Tension Length (L) manually", value=750.0)
  selected_struct_disp = (
      selected_struct if "selected_struct" in locals() else "Manual"
  )

else:
  st.write("🛰️ GPS Mode (Auto-Detect Structure & Temp)")
  location = streamlit_geolocation()

  if location and location.get("latitude"):
    cur_lat = location["latitude"]
    cur_lon = location["longitude"]

    if st.button("🚀 SYNC GPS, WEATHER & NEAREST STRUCTURE"):
      with st.spinner("Syncing GPS & GIS Data..."):
        # 1. Weather Fetch
        st.session_state.temp_val = get_weather_by_coords(cur_lat, cur_lon)

        # 2. Reverse Geocoding for Area Name
        g_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={cur_lat}&lon={cur_lon}"
        g_res = requests.get(
            g_url, headers={"User-Agent": "RailwayTool"}, timeout=5
        ).json()
        st.session_state.area_name = g_res.get(
            "display_name", "Local Section"
        )

        # 3. Nearest Structure Auto-Detection via GIS Sheet
        matched_struct, matched_len, dist = get_nearest_structure_by_gps(
            cur_lat, cur_lon, df
        )
        if matched_struct:
          st.session_state.auto_struct = matched_struct
          st.session_state.auto_length = float(matched_len)
          st.success(
              f"🎯 Auto-Detected Nearest Structure: **{matched_struct}**"
              f" (Distance: {dist}m)"
          )
        else:
          st.warning(
              "⚠️ 150m ke daayre mein koi structure nahi mila. Manual select"
              " karein."
          )
          st.session_state.auto_struct = "Not Found"

  if st.session_state.auto_struct and st.session_state.auto_struct not in [
      "Not Found",
      None,
  ]:
    selected_struct_disp = st.session_state.auto_struct
    L = st.session_state.auto_length
    st.markdown(
        f"<div class='length-display'>Auto-Fetched Structure: "
        f"{selected_struct_disp} | Tension Length (L): {L} m</div>",
        unsafe_allow_html=True,
    )
  else:
    selected_struct_disp = "GPS Active (No Structure Matched)"
    L = st.number_input(
        "Enter Tension Length (L) manually",
        value=st.session_state.auto_length,
    )

st.divider()

# --- 7. DISPLAY & RESULTS ---
st.markdown(
    f"""
    <div class="area-box">
        <div class="area-label">📡 ACTIVE SECTION / LOCATION</div>
        <div class="area-text">{st.session_state.area_name}</div>
    </div>
""",
    unsafe_allow_html=True,
)

theta_2 = st.number_input(
    "Current Temp (°C)", value=st.session_state.temp_val, step=0.1
)

# Calculation Logic (35°C Standard)
delta = L * 0.000017 * (35 - theta_2) * 1000
x_val, y_val = 1300 + delta, 2300 + (3 * delta)

st.divider()
c1, c2 = st.columns(2)
c1.metric("X (Pulley Gap)", f"{round(x_val, 1)} mm")
c2.metric("Y (Weight Height)", f"{round(y_val, 1)} mm")

# --- 8. IMAGE CARD GENERATOR (3K RESOLUTION) ---
ist_offset = timezone(timedelta(hours=5, minutes=30))
curr_dt = datetime.now(ist_offset).strftime("%d-%b-%Y %I:%M:%S %p")

scale = 3
width, height = 900 * scale, 550 * scale
img = Image.new("RGB", (width, height), color="#050a0f")
draw = ImageDraw.Draw(img)

try:
  font_title = ImageFont.load_default(size=25 * scale)
  font_body = ImageFont.load_default(size=17 * scale)
  font_val = ImageFont.load_default(size=20 * scale)
except Exception:
  font_title = font_body = font_val = ImageFont.load_default()

# Outer Border & Title Header
draw.rectangle(
    [20 * scale, 20 * scale, width - 20 * scale, height - 20 * scale],
    outline="#00d4ff",
    width=5 * scale,
)
draw.text(
    (40 * scale, 40 * scale),
    "⚡ OHE ATD SMART TOOL RECORD",
    fill="#00d4ff",
    font=font_title,
)
draw.line(
    [(40 * scale, 100 * scale), (width - 40 * scale, 100 * scale)],
    fill="#00d4ff",
    width=3 * scale,
)

lines = [
    f"📅 Date & Time: {curr_dt}",
    f"📍 Location / Section: {st.session_state.area_name[:40]}",
    f"🏗️ Structure No: {selected_struct_disp}",
    f"📏 Tension Length (L): {L} m",
    f"🌡️ Temperature: {theta_2} °C",
]

y_off = 120 * scale
for line in lines:
  draw.text((40 * scale, y_off), line, fill="#ffffff", font=font_body)
  y_off += 42 * scale

# X & Y Output Box
draw.rectangle(
    [40 * scale, 360 * scale, width - 40 * scale, 500 * scale],
    fill="#1c2128",
    outline="#00ff41",
    width=4 * scale,
)
draw.text(
    (60 * scale, 380 * scale),
    f"Calculated X Value : {x_val:.0f} mm",
    fill="#00ff41",
    font=font_val,
)
draw.text(
    (60 * scale, 435 * scale),
    f"Calculated Y Value : {y_val:.0f} mm",
    fill="#00ff41",
    font=font_val,
)

buf = io.BytesIO()
img.save(buf, format="PNG")

# --- 9. BUTTON & FOOTER ---
st.markdown(
    """<style>
    div[data-testid="stDownloadButton"] {
        display: flex;
        justify-content: center;
        margin-top: 15px;
    }
    div[data-testid="stDownloadButton"] > button {
        background-color: #002b49 !important;
        color: #ccff00 !important;
        border: 2px solid #00d4ff !important;
        font-weight: bold !important;
        font-size: 18px !important;
        width: 240px !important;
        height: 50px !important;
        border-radius: 8px !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #004070 !important;
        color: #ffffff !important;
    }
    </style>""",
    unsafe_allow_html=True,
)


def notify_save():
  st.toast("✅ Image Saved Successfully!", icon="💾")


st.download_button(
    label="💾 SAVE IMG",
    data=buf.getvalue(),
    file_name=f"ATD_Record_{datetime.now(ist_offset).strftime('%Y%m%d_%H%M%S')}.png",
    mime="image/png",
    on_click=notify_save,
)

st.markdown(
    "<div style='text-align: center; font-size: 10px; margin-top: 40px;"
    " opacity: 0.6;'>DEVELOPED BY: A.K.MULCHANDANI JE/TRD</div>",
    unsafe_allow_html=True,
)
