import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import os

# --- Path to data (relative to repo root) ---
path = "Data/Derived_Data"

# --- Streamlit page setup ---
st.set_page_config(page_title="Interactive Hazard Map", layout="wide")
st.title("Interactive Environmental Hazard Map")

# --- Cached function to load GeoDataFrame ---
@st.cache_data
def load_gdf():
    data_file = os.path.join(path, 'cleaned_gdf.geojson')
    return gpd.read_file(data_file)

gdf_merged = load_gdf()

# --- Column rename dictionary ---
column_rename = {
    "haz_idx": "Environmental Hazard Index",
    "pov_idx": "Low Poverty Index",
    "pct_nonwhite": "Percent of Nonwhite Residents",
    "county_name": "County Name",
    "Total_Population_2020": "Total Population (2020)",
    "pct_white": "Percent of White Residents"
}

# --- County filter dropdown ---
county_options = [None] + sorted(gdf_merged["county_name"].dropna().unique())
selected_county = st.selectbox(
    "Filter map by county:",
    county_options,
    format_func=lambda x: "All Counties" if x is None else x
)

# --- Cached function to filter GeoDataFrame by county ---
@st.cache_data
def filter_by_county(_gdf, county):
    if county:
        return _gdf[_gdf["county_name"] == county]
    return _gdf

gdf_filtered = filter_by_county(gdf_merged, selected_county)

# --- User selects numeric column (restricted) ---
# Columns the user is allowed to select for visualization
visual_columns = ["haz_idx", "pov_idx", "pct_nonwhite", "Total_Population_2020", "pct_white"]

# All numeric columns in the dataset
numeric_columns = gdf_merged.select_dtypes(include=["number"]).columns.tolist()

# Keep only the ones we want the user to select
numeric_columns_for_select = [col for col in numeric_columns if col in visual_columns]

# Friendly names for display
friendly_names = [column_rename.get(col, col) for col in numeric_columns_for_select]

selected_friendly_name = st.selectbox(
    "Select a column to visualize:",
    friendly_names,
    index=friendly_names.index(column_rename.get("haz_idx", "haz_idx"))
)

# Map back to raw column name for calculations
selected_column = numeric_columns_for_select[friendly_names.index(selected_friendly_name)]

# --- Cached function to get min/max for colormap ---
@st.cache_data
def get_column_range(_gdf, column):
    return _gdf[column].min(), _gdf[column].max()

col_min, col_max = get_column_range(gdf_filtered, selected_column)

# --- Colormap definitions ---
colormap_options = {
    "Reds": cm.LinearColormap(['#fee5d9','#fcae91','#fb6a4a','#de2d26','#a50f15']),
    "Blues": cm.LinearColormap(['#eff3ff','#bdd7e7','#6baed6','#3182bd','#08519c']),
    "Greens": cm.LinearColormap(['#edf8e9','#bae4b3','#74c476','#31a354','#006d2c']),
    "YlOrRd": cm.LinearColormap(['#ffffb2','#fecc5c','#fd8d3c','#f03b20','#bd0026']),
    "Viridis": cm.LinearColormap(['#440154','#482777','#3e4989','#31688e','#26828e','#1f9e89',
                                  '#35b779','#6ece58','#b5de2b','#fde725']),
    "Plasma": cm.LinearColormap(['#0d0887','#3d049a','#6300a7','#8400b0','#a11fb9','#bd4fc1',
                                 '#d66bb9','#ed91b3','#fbcca0','#f0f921'])
}

cmap_option = st.selectbox("Select a colormap:", list(colormap_options.keys()), index=0)
colormap = colormap_options[cmap_option].scale(col_min, col_max)
colormap.caption = selected_friendly_name

# --- Cached function to convert filtered GeoDataFrame to GeoJSON ---
@st.cache_data
def gdf_to_geojson(_gdf):
    return _gdf.to_json()

geojson_data = gdf_to_geojson(gdf_filtered)

# --- Create Folium map with dynamic zoom ---
if selected_county:
    # Zoom in on selected county
    center = [gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()]
    zoom = 9
else:
    # Show full dataset
    center = [gdf_merged.geometry.centroid.y.mean(), gdf_merged.geometry.centroid.x.mean()]
    zoom = 6

m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")

# --- Style function with safe fallback for missing values ---
def style_function(feature):
    val = feature['properties'].get(selected_column)
    if val is None:
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
tooltip_fields = ['tract', selected_column, 'county_name']
tooltip_aliases = ['Census Tract:', selected_friendly_name, 'County:']

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=tooltip_aliases,
        localize=True
    )
).add_to(m)

# --- Display map in Streamlit ---
st_folium(m, width=800, height=600)
