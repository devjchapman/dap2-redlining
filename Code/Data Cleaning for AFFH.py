import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

try:
    script_dir = Path(__file__).parent
except NameError:
    script_dir = Path.cwd()

# --- Load AFFH ---
url = "https://uchicago.box.com/shared/static/hu6l6g8rdhkxjlly80gq8tgp37fqpgek.csv"
df_affh = pd.read_csv(url, encoding="latin-1")
df_il = df_affh.loc[df_affh["stusab"] == "IL"].copy()

req_cols = [
    "geoid", "haz_idx", "county_name", "stusab",
    "Total_Population2020", "white_2020", "black_2020", "native_2020", "asian_pi_2020", "hisp_2020",
    "pct_white_2020", "pct_black_2020", "pct_native_2020", "pct_asian_pi_2020", "pct_hispanic_2020",
    "pov_idx", "tcost_idx", "pct_poor_ns", "pct_nonwhite",
    "hh_pct_white_lt30ami", "hh_pct_black_lt30ami", "hh_pct_hisp_lt30ami", "hh_pct_ai_pi_lt30ami",
    "state", "state_name", "county", "tract"
]

# Only keep columns that actually exist in the dataframe
available_cols = [c for c in req_cols if c in df_affh.columns]
missing_cols = [c for c in req_cols if c not in df_affh.columns]
if missing_cols:
    print(f"Warning: These columns were not found and will be skipped: {missing_cols}")

df_small = df_il[available_cols].copy()

# IMPORTANT: keep GEOID as zero-padded string
df_small["geoid"] = df_small["geoid"].astype(str).str.zfill(11)

# --- Load tracts (Illinois shapefile) ---
# Fix: Added missing slash — '../Data/...' not '..Data/...'
tracts_path = (script_dir / "../Data/Derived_Data/tl_2025_17_tract/tl_2025_17_tract.shp").resolve()

if not tracts_path.exists():
    raise FileNotFoundError(f"Shapefile not found at: {tracts_path}")

tracts = gpd.read_file(tracts_path)
tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)

# --- Merge: KEEP ALL TRACTS ---
gdf = tracts.merge(df_small, left_on="GEOID", right_on="geoid", how="left")
gdf = gdf.to_crs("EPSG:4326")

# --- Save output ---
# Fix: Added missing slash — '../Data/...' not '..Data/...'
output_dir = (script_dir / "../Data/Derived_Data").resolve()
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "merged_gdf.gpkg"
gdf.to_file(output_path, driver="GPKG")