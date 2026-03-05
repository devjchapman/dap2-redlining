# Data Center Impact on Illinois
## View our app at: https://dap2-bcd.streamlit.app/

Affirmatively Furthering Fair Housing Data and Mapping Tool data: https://uchicago.box.com/shared/static/hu6l6g8rdhkxjlly80gq8tgp37fqpgek.csv <br>
use the AFFH_tract_AFFHT0007_December2024.csv file and run the Data Cleaning for AFFH.py file to create the gdf.csv file for use

gdf_merged geopackage for streamlit found at: https://uchicago.box.com/shared/static/5mirakc5f539szi8kqwckt4tt493vm6y.gpkg

## Setup

```bash
conda env create -f requirements.txt
```

## Project Structure

```
data/
  Raw_data/           # Raw data files
    im3_open_source_data_center_atlas.gpkg  # datacenter data
  Derived_data/       # Filtered data and output plots
    tl_2025_17_tract   # geodata
    gdf_merged.csv(.gpkg)    # 2020 Illinois data on environmental conditions and demographics
code/
  Data Cleaning for AFFH.py    # Filters data to illinois
  data_center_map.py            # Plots datacenters
  envhaz_plot.py                # Plots environmental hazard index across Illinois
  poverty_plot.py               # Plots poverty index across Illinois
```

## Usage

1. Run preprocessing to filter data:
   ```bash
   python code/Data Cleaning for AFFH.py
   ```

2. Generate the datacenter plot:
   ```bash
   python code/data_center_map.py
   ```

3. Streamlit (https://dap2-bcd.streamlit.app/)
   ```bash
   python code/app.py
   ```
   Note that the Streamlit App must be woken up if it has not been run in 24 hours.
   
