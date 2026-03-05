import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import geopandas as gpd
from pathlib import Path
import folium
from streamlit_folium import st_folium
import branca.colormap as cm
import requests

# =========================
# CONFIG
# =========================

GPKG_URL = "https://uchicago.box.com/shared/static/5mirakc5f539szi8kqwckt4tt493vm6y.gpkg"

# Data center CSV (repo-relative).
DATA_CENTER_CSV = "Data/Raw_Data/data_center_geodata/im3_open_source_data_center_atlas/im3_open_source_data_center_atlas.csv"

# =========================
# PATHS
# =========================
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent  # Code/ -> repo root
DERIVED_DIR = (REPO_ROOT / "Data" / "Derived_Data").resolve()
DERIVED_DIR.mkdir(parents=True, exist_ok=True)
GPKG_PATH = (DERIVED_DIR / "gdf_merged.gpkg").resolve()

# =========================
# STREAMLIT SETUP
# =========================
st.set_page_config(page_title="Environmental Hazard Map", layout="wide")

# =========================
# HELPERS
# =========================
@st.cache_data(show_spinner=True)
def ensure_gpkg(local_path_str: str, url: str) -> str:
    """
    Download gdf_merged.gpkg at runtime if missing/invalid.
    Validates that the file is SQLite (GeoPackage) not HTML.
    """
    local_path = Path(local_path_str)

    if not url or "PASTE_DIRECT_DOWNLOAD_URL" in url:
        raise ValueError(
            "GPKG_URL is not set. Replace it with a direct-download URL to gdf_merged.gpkg "
            "(must not return HTML)."
        )

    # Heuristic: < 200KB is very likely invalid for a tract-level gpkg
    if (not local_path.exists()) or (local_path.stat().st_size < 200_000):
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=180,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as r:
            r.raise_for_status()

            ct = (r.headers.get("Content-Type") or "").lower()
            if "text/html" in ct:
                preview = r.text[:500]
                raise RuntimeError(
                    "Download URL returned HTML (not a .gpkg). You need a direct-download link.\n"
                    f"Content-Type: {ct}\n\nPreview:\n{preview}"
                )

            tmp_path = local_path.with_suffix(".tmp")
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            tmp_path.replace(local_path)

    # Validate GeoPackage signature: GeoPackage is SQLite => header starts with "SQLite format 3"
    head = local_path.read_bytes()[:16]
    if not head.startswith(b"SQLite format 3"):
        # try to decode for a useful error
        try:
            txt = local_path.read_bytes()[:200].decode("utf-8", errors="replace")
        except Exception:
            txt = "<could not decode>"
        raise RuntimeError(
            "Downloaded file is not a valid GeoPackage (expected SQLite header 'SQLite format 3').\n"
            f"First 200 bytes:\n{txt}"
        )

    return str(local_path)


@st.cache_data(show_spinner=True)
def load_gdf(gpkg_path_str: str) -> gpd.GeoDataFrame:
    # Prefer Fiona engine if available, but don't hard-require it.
    try:
        return gpd.read_file(gpkg_path_str, layer="merged_layer", engine="fiona")
    except Exception:
        return gpd.read_file(gpkg_path_str, layer="merged_layer")


@st.cache_data(show_spinner=True)
def load_data_centers(csv_rel_path: str) -> pd.DataFrame:
    csv_path = (REPO_ROOT / csv_rel_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Data center CSV not found at: {csv_path}\n"
            "Update DATA_CENTER_CSV to the correct relative path in your repo."
        )
    df = pd.read_csv(csv_path)
    # Standardize expected columns
    for c in ["lat", "lon"]:
        if c not in df.columns:
            raise ValueError(f"Data center CSV is missing required column '{c}'. Found: {list(df.columns)}")
    df = df.dropna(subset=["lat", "lon"]).copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).copy()
    return df


def safe_center_latlon(gdf: gpd.GeoDataFrame) -> list[float]:
    # Center on centroid mean (good enough for map centering)
    return [float(gdf.geometry.centroid.y.mean()), float(gdf.geometry.centroid.x.mean())]


def make_colormap(gdf: gpd.GeoDataFrame, column: str, cmap_name: str):
    colormap_options = {
        "Reds": cm.LinearColormap(["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]),
        "Blues": cm.LinearColormap(["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]),
        "Greens": cm.LinearColormap(["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"]),
        "YlOrRd": cm.LinearColormap(["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]),
        "Viridis": cm.LinearColormap(
            ["#440154", "#482777", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"]
        ),
        "Plasma": cm.LinearColormap(
            ["#0d0887", "#3d049a", "#6300a7", "#8400b0", "#a11fb9", "#bd4fc1", "#d66bb9", "#ed91b3", "#fbcca0", "#f0f921"]
        ),
    }

    col_min = float(pd.to_numeric(gdf[column], errors="coerce").min())
    col_max = float(pd.to_numeric(gdf[column], errors="coerce").max())
    if not np.isfinite(col_min) or not np.isfinite(col_max) or col_min == col_max:
        # fallback if constant / missing
        col_min, col_max = 0.0, 1.0

    colormap = colormap_options[cmap_name].scale(col_min, col_max)
    colormap.caption = column
    return colormap


# =========================
# SIDEBAR NAVIGATION
# =========================
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select page",
    ["Welcome", "Data Centers Map", "Comparison Dashboard"],
)

# =========================
# PAGE: WELCOME
# =========================
if page == "Welcome":
    st.title("Environmental Hazard Map of Illinois")

    st.markdown(
        """
### What this app does
This Streamlit app provides tract-level views of environmental hazard indicators across Illinois plus an overlay of data center locations and a comparison dashboard.

### Pages
- **Data Centers Map**: hazard choropleth + point overlay of data center locations.
- **Comparison Dashboard**: county-level summaries and distributions with interactive charts.

### Notes
- The tract dataset is loaded from a **GeoPackage** (`gdf_merged.gpkg`). If it isn’t available in the repo (e.g., Git LFS), the app downloads it from `GPKG_URL`.
- Data centers are loaded from the CSV specified by `DATA_CENTER_CSV`.
        """
    )

    st.info("Use the sidebar to open the Data Centers Map or the Comparison Dashboard.")

# =========================
# COMMON: LOAD TRACTS (ONLY WHEN NEEDED)
# =========================
def get_tracts() -> gpd.GeoDataFrame:
    gpkg_local = ensure_gpkg(str(GPKG_PATH), GPKG_URL)
    gdf = load_gdf(gpkg_local)

    # Ensure WGS84 for Folium
    try:
        if gdf.crs is None or str(gdf.crs).lower() != "epsg:4326":
            gdf = gdf.to_crs("EPSG:4326")
    except Exception:
        # if CRS conversion fails, continue; map might be off but app won't crash
        pass

    return gdf

# =========================
# PAGE: DATA CENTERS MAP
# =========================
if page == "Data Centers Map":
    st.title("Hazard Map with Data Center Locations")

    gdf_merged = get_tracts()
    data_centers = load_data_centers(DATA_CENTER_CSV)

    # Controls
    left, right = st.columns([1, 1])

    with left:
        if "county_name" in gdf_merged.columns:
            county_options = [None] + sorted(gdf_merged["county_name"].dropna().unique().tolist())
        else:
            county_options = [None]

        selected_county = st.selectbox(
            "Filter tracts by county:",
            county_options,
            format_func=lambda x: "All Counties" if x is None else x,
        )

        numeric_columns = gdf_merged.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_columns:
            st.error("No numeric columns found to visualize.")
            st.stop()

        selected_column = st.selectbox(
            "Hazard variable for choropleth:",
            numeric_columns,
            index=numeric_columns.index("haz_idx") if "haz_idx" in numeric_columns else 0,
        )

    with right:
        cmap_option = st.selectbox("Colormap:", ["Reds", "Blues", "Greens", "YlOrRd", "Viridis", "Plasma"], index=0)
        point_radius = st.slider("Data center point radius (px)", min_value=2, max_value=10, value=5)
        show_points = st.checkbox("Show data center points", value=True)

    if selected_county and "county_name" in gdf_merged.columns:
        gdf_filtered = gdf_merged[gdf_merged["county_name"] == selected_county].copy()
    else:
        gdf_filtered = gdf_merged.copy()

    colormap = make_colormap(gdf_filtered, selected_column, cmap_option)

    # Build map
    center = safe_center_latlon(gdf_filtered)
    m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")

    def style_function(feature):
        val = feature["properties"].get(selected_column)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return {"fillColor": "#cccccc", "color": "#b0b0b0", "weight": 0.6, "fillOpacity": 0.7}
        return {"fillColor": colormap(val), "color": "#b0b0b0", "weight": 0.6, "fillOpacity": 0.7}

    tooltip_fields = [c for c in ["geoid_id", selected_column] if c in gdf_filtered.columns]
    tooltip_aliases = []
    for c in tooltip_fields:
        tooltip_aliases.append("geoid_id:" if c == "geoid_id" else f"{c}:")

    folium.GeoJson(
        gdf_filtered.to_json(),
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, localize=True),
        name="Tracts",
    ).add_to(m)

    # Overlay data centers
    if show_points:
        # Basic tooltip fields if available
        candidate_cols = ["name", "operator", "site_name", "county", "city", "state", "capacity_mw"]
        tooltip_cols = [c for c in candidate_cols if c in data_centers.columns]
        for _, row in data_centers.iterrows():
            tip = None
            if tooltip_cols:
                lines = []
                for c in tooltip_cols:
                    v = row.get(c)
                    if pd.notna(v):
                        lines.append(f"{c}: {v}")
                tip = "\n".join(lines) if lines else None

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=point_radius,
                weight=1,
                opacity=0.9,
                fill=True,
                fill_opacity=0.8,
                tooltip=tip,
            ).add_to(m)

    colormap.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, width=950, height=650)

# =========================
# PAGE: COMPARISON DASHBOARD
# =========================
if page == "Comparison Dashboard":
    st.title("Comparison Dashboard (County Summaries)")

    gdf_merged = get_tracts()

    if "county_name" not in gdf_merged.columns:
        st.error("Expected 'county_name' column not found in tract GeoDataFrame.")
        st.stop()

    numeric_columns = gdf_merged.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_columns:
        st.error("No numeric columns found to analyze.")
        st.stop()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        metric = st.selectbox(
            "Metric to compare (tract-level):",
            numeric_columns,
            index=numeric_columns.index("haz_idx") if "haz_idx" in numeric_columns else 0,
        )

    with col2:
        agg = st.selectbox("County aggregation", ["mean", "median", "p90"], index=0)

    with col3:
        top_n = st.slider("Show top N counties", min_value=5, max_value=40, value=20)

    # Prepare county summary
    df = gdf_merged[["county_name", metric]].copy()
    df[metric] = pd.to_numeric(df[metric], errors="coerce")

    if agg == "mean":
        summary = df.groupby("county_name", as_index=False)[metric].mean()
        agg_label = "Mean"
    elif agg == "median":
        summary = df.groupby("county_name", as_index=False)[metric].median()
        agg_label = "Median"
    else:
        summary = df.groupby("county_name", as_index=False)[metric].quantile(0.90)
        agg_label = "P90"

    summary = summary.dropna(subset=[metric]).sort_values(metric, ascending=False).head(top_n)

    st.subheader(f"{agg_label} {metric} by County (Top {top_n})")
    bar = (
        alt.Chart(summary)
        .mark_bar()
        .encode(
            x=alt.X(metric, title=f"{agg_label} {metric}"),
            y=alt.Y("county_name:N", sort="-x", title="County"),
            tooltip=["county_name", alt.Tooltip(metric, format=".3f")],
        )
        .properties(height=22 * len(summary))
    )
    st.altair_chart(bar, width="stretch")

    st.subheader("Distribution of Tract Values by County")
    # choose a subset of counties for boxplot to keep it readable
    counties_for_dist = st.multiselect(
        "Counties to include in distribution plot",
        options=sorted(df["county_name"].dropna().unique().tolist()),
        default=summary["county_name"].tolist()[: min(8, len(summary))],
    )
    df_dist = df[df["county_name"].isin(counties_for_dist)].dropna(subset=[metric]).copy()

    if df_dist.empty:
        st.warning("No data available for the selected counties/metric.")
    else:
        box = (
            alt.Chart(df_dist)
            .mark_boxplot()
            .encode(
                x=alt.X("county_name:N", sort=counties_for_dist, title="County"),
                y=alt.Y(metric, title=metric),
                tooltip=["county_name", alt.Tooltip(metric, format=".3f")],
            )
            .properties(height=420)
        )
        st.altair_chart(box, width="stretch")

    st.subheader("Download county summary")
    st.download_button(
        "Download CSV",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name=f"county_{agg}_{metric}_top{top_n}.csv",
        mime="text/csv",
    )
