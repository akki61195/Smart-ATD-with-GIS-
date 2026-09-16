from datetime import datetime, timezone, timedelta
import io
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
import streamlit as st
from streamlit_geolocation import streamlit_geolocation

# --- 1. PAGE SETUP & HIGH CONTRAST CSS ---
st.set_page_config(
    page_title="OHE ATD Smart Tool (Dual Mode)", page_icon="⚡", layout="centered"
)

st.markdown(
    """
    <style>
    .stApp { background-color: #050a0f; color: white; }
    
    /* Make all labels, radios, checkboxes, and text bright white */
    label, .stRadio label, .stCheckbox label, p, span {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    
    /* Bright Metric Titles and Values */
    [data-testid="stMetricLabel"] {
        color: #00d4ff !important;
        font-size: 16px !important;
        font-weight: bold !important;
    }
    [data-testid="stMetricValue"] {
        color: #00ff41 !important;
        font-size: 26px !important;
        font-weight: bold !important;
    }

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

    /* Save Button Styling: Black Background with Accent Line Color Text/Border */
    div[data-testid="stDownloadButton"] {
        display: flex;
        justify-content: center;
        margin-top: 15px;
    }
    div[data-testid="stDownloadButton"] > button {
        background-color: #000000 !important;
        color: #00d4ff !important;
        border: 2px solid #00d4ff !important;
        font-weight: bold !important;
        font-size: 18px !important;
        width: 240px !important;
        height: 50px !important;
        border-radius: 8px !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #1c2128 !important;
        color: #ffffff !important;
        border-color: #00ff41 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 2. TOP MODE SELECTION BUTTONS ---
st.markdown(
    "<h2 style='text-align: center; color: #00d4ff;'>⚡ OHE ATD Smart"
    " Tool</h2>",
    unsafe_allow_html=True,
)

app_mode = st.radio(
    "Select Operation Mode",
    ["Manual Mode (Standard)", "GIS Mode (Auto-Detect)"],
    horizontal=True,
)

st.divider()

# --- COMMON WEATHER & GIS ENGINES ---
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


def get_nearest_structure_by_gps(current_lat, current_lon, df):
  if (
      df is None
      or "Latitude" not in df.columns
      or "Longitude" not in df.columns
  ):
    return None, None, None
  lat1, lon1 = np.radians(current_lat), np.radians(current_lon)
  lat2, lon2 = np.radians(df["Latitude"]), np.radians(df["Longitude"])
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = (
      np.sin(dlat / 2.0) ** 2
      + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
  )
  c = 2 * np.arcsin(np.sqrt(a))
  distance_meters = 6367 * c * 1000
  min_idx = distance_meters.idxmin()
  nearest_dist = distance_meters[min_idx]
  if nearest_dist <= 50:  # Updated to 50 meters range
    return (
        df.loc[min_idx, "Structure_No"],
        df.loc[min_idx, "Tension_Length"],
        round(nearest_dist, 1),
    )
  return None, None, None


# --- HIGH QUALITY HD PORTRAIT IMAGE GENERATOR FUNCTION (2X SCALE) ---
def generate_portrait_atd_image(
    title_str, curr_dt, area_text, struct_disp, L, theta_2, x_val, y_val
):
  scale = 2  # 2X scaling for crisp high-definition image quality
  width, height = 1000 * scale, 1350 * scale
  img = Image.new("RGB", (width, height), color="#050a0f")
  draw = ImageDraw.Draw(img)

  # Load scaled TrueType Fonts with graceful fallback
  try:
    font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 38 * scale)
    font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 28 * scale)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 26 * scale)
    font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 26 * scale)
    font_val = ImageFont.truetype("DejaVuSans-Bold.ttf", 42 * scale)
  except:
    try:
      font_title = ImageFont.truetype("arialbd.ttf", 38 * scale)
      font_header = ImageFont.truetype("arialbd.ttf", 28 * scale)
      font_body = ImageFont.truetype("arial.ttf", 26 * scale)
      font_bold = ImageFont.truetype("arialbd.ttf", 26 * scale)
      font_val = ImageFont.truetype("arialbd.ttf", 42 * scale)
    except:
      font_title = ImageFont.load_default()
      font_header = ImageFont.load_default()
      font_body = ImageFont.load_default()
      font_bold = ImageFont.load_default()
      font_val = ImageFont.load_default()

  # Outer Neon Border
  draw.rectangle(
      [25 * scale, 25 * scale, width - 25 * scale, height - 25 * scale],
      outline="#00d4ff",
      width=5 * scale,
  )

  # Title & Divider Line
  draw.text((50 * scale, 50 * scale), title_str, fill="#00d4ff", font=font_title)
  draw.line(
      [(50 * scale, 110 * scale), (width - 50 * scale, 110 * scale)],
      fill="#00d4ff",
      width=3 * scale,
  )

  # Compact Information Rows
  lines_data = [
      ("📅 Date & Time:", curr_dt),
      (
          "📍 Location / Section:",
          area_text[:45] + ("..." if len(area_text) > 45 else ""),
      ),
      ("🏗️ Structure No:", str(struct_disp)),
      ("📏 Tension Length (L):", f"{L} m"),
      ("🌡️ Temperature:", f"{theta_2} °C"),
  ]

  y_off = 150 * scale
  for label, val in lines_data:
    draw.text((50 * scale, y_off), label, fill="#00d4ff", font=font_bold)
    draw.text((360 * scale, y_off), str(val), fill="#ffffff", font=font_body)
    y_off += 65 * scale  # Compact spacing

  # Results Box (X & Y values)
  box_top = y_off + 20 * scale
  box_bottom = box_top + 320 * scale
  draw.rectangle(
      [50 * scale, box_top, width - 50 * scale, box_bottom],
      fill="#1c2128",
      outline="#00ff41",
      width=4 * scale,
  )

  draw.text(
      (80 * scale, box_top + 35 * scale),
      "Calculated X Value (Pulley Gap):",
      fill="#ffffff",
      font=font_header,
  )
  draw.text(
      (80 * scale, box_top + 80 * scale),
      f"{x_val:.1f} mm",
      fill="#00ff41",
      font=font_val,
  )

  draw.text(
      (80 * scale, box_top + 165 * scale),
      "Calculated Y Value (Weight Height):",
      fill="#ffffff",
      font=font_header,
  )
  draw.text(
      (80 * scale, box_top + 210 * scale),
      f"{y_val:.1f} mm",
      fill="#00ff41",
      font=font_val,
  )

  # Footer Credit inside image
  draw.text(
      (width / 2 - 240 * scale, height - 60 * scale),
      "DEVELOPED BY: A.K.MULCHANDANI JE/TRD",
      fill="#aaaaaa",
      font=font_body,
  )

  buf = io.BytesIO()
  img.save(buf, format="PNG")
  return buf.getvalue()


ist_offset = timezone(timedelta(hours=5, minutes=30))

# ==========================================
# A) MANUAL MODE (Purana App + Purana Sheet)
# ==========================================
if app_mode == "Manual Mode (Standard)":
  OLD_SHEET_ID = "1vfioGSmpC7a5S8SMUpCk9xn-mtttvcTecLEQ1Sd6XkU"
  OLD_SHEET_URL = (
      f"https://docs.google.com/spreadsheets/d/{OLD_SHEET_ID}/export?format=csv"
  )


  @st.cache_data
  def load_old_sheet():
    try:
      df = pd.read_csv(OLD_SHEET_URL)
      df.columns = df.columns.str.strip()
      return df
    except:
      return None


  df_old = load_old_sheet()

  if "m_temp" not in st.session_state:
    st.session_state.m_temp = 35.0
  if "m_area" not in st.session_state:
    st.session_state.m_area = "GPS Not Active"

  # Structure Selection
  if df_old is not None:
    struct_list = df_old["Structure_No"].dropna().unique().tolist()
    selected_struct = st.selectbox(
        "📍 Select Structure No", ["Manual Entry"] + struct_list
    )
    if selected_struct != "Manual Entry":
      L = float(
          df_old[df_old["Structure_No"] == selected_struct][
              "Tension_Length"
          ].values[0]
      )
      st.markdown(
          f"<div class='length-display'>Tension Length (L): {L} m</div>",
          unsafe_allow_html=True,
      )
    else:
      L = st.number_input("Enter Tension Length (L) manually", value=750.0)
  else:
    L = st.number_input("Enter Tension Length (L) manually", value=750.0)

  st.divider()
  manual_loc = st.checkbox("✍️ Enter Location Manually", key="m_check")

  if manual_loc:
    city_input = st.text_input("Enter City Name", value="Kodinar")
    if st.button("🔍 FETCH TEMP FOR THIS CITY"):
      with st.spinner("Fetching data..."):
        t, a = get_manual_city_data(city_input)
        st.session_state.m_temp = t
        st.session_state.m_area = a
  else:
    st.write("🛰️ GPS Mode")
    location = streamlit_geolocation()
    if location and location.get("latitude"):
      if st.button("🌡️ SYNC LIVE AREA & TEMP"):
        with st.spinner("Syncing..."):
          st.session_state.m_temp = get_weather_by_coords(
              location["latitude"], location["longitude"]
          )
          g_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={location['latitude']}&lon={location['longitude']}"
          g_res = requests.get(
              g_url, headers={"User-Agent": "RailwayTool"}, timeout=5
          ).json()
          st.session_state.m_area = g_res.get("display_name", "Local Section")

  st.markdown(
      f"""
        <div class="area-box">
            <div class="area-label">📡 ACTIVE SECTION</div>
            <div class="area-text">{st.session_state.m_area}</div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  theta_2 = st.number_input(
      "Current Temp (°C)", value=st.session_state.m_temp, step=0.1, key="m_t"
  )
  delta = L * 0.000017 * (35 - theta_2) * 1000
  x_val, y_val = 1300 + delta, 2300 + (3 * delta)

  st.divider()
  c1, c2 = st.columns(2)
  c1.metric("X (Pulley Gap)", f"{round(x_val, 1)} mm")
  c2.metric("Y (Weight Height)", f"{round(y_val, 1)} mm")

  # Generate Portrait Image for Manual Mode
  curr_dt = datetime.now(ist_offset).strftime("%d-%b-%Y %I:%M:%S %p")
  struct_disp = (
      selected_struct if "selected_struct" in locals() else "Manual Entry"
  )
  img_bytes = generate_portrait_atd_image(
      "⚡ OHE ATD SMART RECORD",
      curr_dt,
      st.session_state.m_area,
      struct_disp,
      L,
      theta_2,
      x_val,
      y_val,
  )


  def notify_save_m():
    st.toast("✅ Image Saved Successfully!", icon="💾")


  st.download_button(
      label="💾 SAVE IMG",
      data=img_bytes,
      file_name=f"ATD_Manual_{datetime.now(ist_offset).strftime('%Y%m%d_%H%M%S')}.png",
      mime="image/png",
      on_click=notify_save_m,
  )


# ==========================================
# B) GIS MODE (Clean Auto-Sync Version)
# ==========================================
else:
  NEW_SHEET_ID = "1VYubXUbniIrCNZlybPQD8lC71SS2wBYlR-kF_EtD5IY"
  NEW_SHEET_URL = (
      f"https://docs.google.com/spreadsheets/d/{NEW_SHEET_ID}/export?format=csv"
  )


  @st.cache_data
  def load_gis_sheet():
    try:
      df = pd.read_csv(NEW_SHEET_URL)
      df.columns = df.columns.str.strip()
      return df
    except:
      return None


  df_gis = load_gis_sheet()

  if "g_temp" not in st.session_state:
    st.session_state.g_temp = 35.0
  if "g_area" not in st.session_state:
    st.session_state.g_area = "GPS Not Active"
  if "g_struct" not in st.session_state:
    st.session_state.g_struct = "Not Detected"
  if "g_length" not in st.session_state:
    st.session_state.g_length = 750.0

  # Automatic Geolocation Fetch
  location_g = streamlit_geolocation()

  # Single Clean Auto-Sync Button
  if st.button("🚀 AUTO-SYNC STRUCTURE, WEATHER & GPS"):
    if location_g and location_g.get("latitude"):
      cur_lat = location_g["latitude"]
      cur_lon = location_g["longitude"]
      with st.spinner("Syncing GIS Data & Nearest Structure (50m range)..."):
        # 1. Weather
        st.session_state.g_temp = get_weather_by_coords(cur_lat, cur_lon)

        # 2. Area Name via Reverse Geocoding
        g_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={cur_lat}&lon={cur_lon}"
        g_res = requests.get(
            g_url, headers={"User-Agent": "RailwayTool"}, timeout=5
        ).json()
        st.session_state.g_area = g_res.get("display_name", "Local Section")

        # 3. Nearest Structure Matching (50m threshold)
        matched_struct, matched_len, dist = get_nearest_structure_by_gps(
            cur_lat, cur_lon, df_gis
        )
        if matched_struct:
          st.session_state.g_struct = matched_struct
          st.session_state.g_length = float(matched_len)
          st.success(
              f"🎯 Auto-Detected Structure: **{matched_struct}** (Distance:"
              f" {dist}m)"
          )
        else:
          st.warning(
              "⚠️ 50m ke daayre mein koi structure nahi mila. Neeche se"
              " manually select karein."
          )
          st.session_state.g_struct = "Not Found"
    else:
      st.error(
          "⚠️ GPS location not available. Please allow location access in your"
          " browser."
      )

  # Display Structure and Tension Length
  if (
      st.session_state.g_struct
      and st.session_state.g_struct not in ["Not Found", "Not Detected", None]
  ):
    selected_struct_disp = st.session_state.g_struct
    L = st.session_state.g_length
    st.markdown(
        f"<div class='length-display'>Structure: {selected_struct_disp} |"
        f" Tension Length (L): {L} m</div>",
        unsafe_allow_html=True,
    )
  else:
    if df_gis is not None:
      struct_list_g = df_gis["Structure_No"].dropna().unique().tolist()
      selected_struct_g = st.selectbox(
          "📍 Select Structure Manually (Fallback)",
          ["Select Structure"] + struct_list_g,
          key="g_sel_fallback",
      )
      if selected_struct_g != "Select Structure":
        L = float(
            df_gis[df_gis["Structure_No"] == selected_struct_g][
                "Tension_Length"
            ].values[0]
        )
        selected_struct_disp = selected_struct_g
        st.markdown(
            f"<div class='length-display'>Tension Length (L): {L} m</div>",
            unsafe_allow_html=True,
        )
      else:
        L = 750.0
        selected_struct_disp = "Not Selected"
    else:
      L = st.number_input(
          "Enter Tension Length (L) manually",
          value=st.session_state.g_length,
          key="g_l_fallback",
      )
      selected_struct_disp = "Manual"

  st.markdown(
      f"""
        <div class="area-box">
            <div class="area-label">📡 ACTIVE SECTION / GIS LOCATION</div>
            <div class="area-text">{st.session_state.g_area}</div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  theta_2 = st.number_input(
      "Current Temp (°C)", value=st.session_state.g_temp, step=0.1, key="g_t"
  )
  delta = L * 0.000017 * (35 - theta_2) * 1000
  x_val, y_val = 1300 + delta, 2300 + (3 * delta)

  st.divider()
  c1, c2 = st.columns(2)
  c1.metric("X (Pulley Gap)", f"{round(x_val, 1)} mm")
  c2.metric("Y (Weight Height)", f"{round(y_val, 1)} mm")

  # Generate High-Resolution Portrait Image for GIS Mode
  curr_dt = datetime.now(ist_offset).strftime("%d-%b-%Y %I:%M:%S %p")
  img_bytes_g = generate_portrait_atd_image(
      "⚡ OHE ATD GIS SMART RECORD",
      curr_dt,
      st.session_state.g_area,
      selected_struct_disp,
      L,
      theta_2,
      x_val,
      y_val,
  )


  def notify_save_g():
    st.toast("✅ HD GIS Image Saved Successfully!", icon="💾")


  st.download_button(
      label="💾 SAVE GIS IMG",
      data=img_bytes_g,
      file_name=f"ATD_GIS_{datetime.now(ist_offset).strftime('%Y%m%d_%H%M%S')}.png",
      mime="image/png",
      on_click=notify_save_g,
  )

st.markdown(
    "<div style='text-align: center; font-size: 10px; margin-top: 40px;"
    " opacity: 0.6;'>DEVELOPED BY: A.K.MULCHANDANI JE/TRD</div>",
    unsafe_allow_html=True,
)
