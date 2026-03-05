import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import geopandas as gpd
import os
import time
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import branca.colormap as cm

path = "Data/Derived_Data"

# --- Streamlit page setup ---
st.set_page_config(page_title="Interactive Hazard Map", layout="wide")
st.title("Interactive Environmental Hazard Map")

# --- Load GeoDataFrame ---
@st.cache_data
def load_gdf():
    return gpd.read_file(os.path.join(path, 'gdf_merged.gpkg'), layer="merged_layer")

gdf_merged = load_gdf()

# --- County filter dropdown ---
county_options = [None] + sorted(gdf_merged["county_name"].dropna().unique())

selected_county = st.selectbox(
    "Filter map by county:",
    county_options,
    format_func=lambda x: "All Counties" if x is None else x
)

# Apply filter only if a county is selected
if selected_county:
    gdf_filtered = gdf_merged[gdf_merged["county_name"] == selected_county]
else:
    gdf_filtered = gdf_merged

# --- User selects numeric column ---
numeric_columns = gdf_merged.select_dtypes(include=["number"]).columns.tolist()
selected_column = st.selectbox(
    "Select a column to visualize:",
    numeric_columns,
    index=numeric_columns.index("haz_idx") if "haz_idx" in numeric_columns else 0
)

# --- Colormap definitions ---
colormap_options = {
    "Reds": cm.LinearColormap(['#fee5d9','#fcae91','#fb6a4a','#de2d26','#a50f15']),
    "Blues": cm.LinearColormap(['#eff3ff','#bdd7e7','#6baed6','#3182bd','#08519c']),
    "Greens": cm.LinearColormap(['#edf8e9','#bae4b3','#74c476','#31a354','#006d2c']),
    "YlOrRd": cm.LinearColormap(['#ffffb2','#fecc5c','#fd8d3c','#f03b20','#bd0026']),
    "Viridis": cm.LinearColormap(['#440154','#482777','#3e4989','#31688e','#26828e','#1f9e89','#35b779','#6ece58','#b5de2b','#fde725']),
    "Plasma": cm.LinearColormap(['#0d0887','#3d049a','#6300a7','#8400b0','#a11fb9','#bd4fc1','#d66bb9','#ed91b3','#fbcca0','#f0f921'])
}

cmap_option = st.selectbox("Select a colormap:", list(colormap_options.keys()), index=0)
col_min = gdf_filtered[selected_column].min()
col_max = gdf_filtered[selected_column].max()
colormap = colormap_options[cmap_option].scale(col_min, col_max)
colormap.caption = selected_column

# --- Create Folium map centered on data ---
center = [gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()]
m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")

# --- Style function with safe fallback for missing values ---
def style_function(feature):
    val = feature['properties'].get(selected_column)
    if val is None:
        # fallback color for missing data
        return {
            'fillColor': '#cccccc',
            'color': '#b0b0b0',
            'weight': 0.6,
            'fillOpacity': 0.7
        }
    return {
        'fillColor': colormap(val),
        'color': '#b0b0b0',
        'weight': 0.6,
        'fillOpacity': 0.7
    }

# --- Add GeoJSON layer with hover tooltip ---
folium.GeoJson(
    gdf_filtered.to_json(),
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=['geoid_id', selected_column],
        aliases=['geoid_id:', f'{selected_column}:'],
        localize=True
    )
).add_to(m)

# --- Add colormap legend ---
colormap.add_to(m)

# --- Display map in Streamlit ---
st_folium(m, width=800, height=600)
