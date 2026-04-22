import os
import sys
from pathlib import Path
sys.path.insert(0, r'E:\00_Commute_Scenario_Research')

import pandas as pd
import geopandas as gpd
import transbigdata as tbd

from src import OD_FEATURE_CSV, SHP_PATH, get_result_path
from src.data_prep import load_fence

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")\nif not MAPBOX_TOKEN:\n    raise RuntimeError("MAPBOX_TOKEN is not set")
BOUNDS = [112.703, 27.92, 113.284, 28.5]
OUTPUT_SECTION = '3.Situation_Diagnosis/3.1Holistic_Diagnosis/3.1.2Dynamic_Stats'

tbd.set_mapboxtoken(MAPBOX_TOKEN)
tbd.set_imgsavepath(r'E:\00_Commute_Scenario_Research\tempt\tileimg')

print('Loading data...')
fence = load_fence(SHP_PATH)
df_od_full = pd.read_csv(OD_FEATURE_CSV, encoding='utf-8-sig')
df_od_full = df_od_full.rename(columns={'Htaz': 'o', 'Jtaz': 'd'})

fence_pts = fence[['taz', 'center_x', 'center_y']].copy()
fence_pts['taz'] = fence_pts['taz'].astype(int)

people_col = [c for c in df_od_full.columns if '人数' in c][0]
df_od = df_od_full[['o', 'd']].copy()
df_od['count'] = df_od_full[people_col]
df_od['o'] = df_od['o'].astype(int)
df_od['d'] = df_od['d'].astype(int)
df_od = df_od.merge(fence_pts.rename(columns={'taz': 'o', 'center_x': 'slon', 'center_y': 'slat'}), on='o', how='inner')
df_od = df_od.merge(fence_pts.rename(columns={'taz': 'd', 'center_x': 'elon', 'center_y': 'elat'}), on='d', how='inner')

print(f'OD data: {len(df_od)} rows')

# Generate OD flowmap with keplergl
print('Generating OD flowmap (keplergl, mincount=2)...')
vmap = tbd.visualization_od(
    df_od,
    col=['slon', 'slat', 'elon', 'elat', 'count'],
    zoom='auto',
    height=800,
    accuracy=500,
    mincount=2
)

html_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.html')
vmap.save_to_html(str(html_path))
print(f'HTML saved: {html_path}')

# Screenshot with playwright
print('Taking screenshot with playwright...')
from playwright.sync_api import sync_playwright

png_path = get_result_path(OUTPUT_SECTION, 'star_OD流线图_实际格局.png')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto(f'file:///{html_path.as_posix()}')
    page.wait_for_timeout(8000)
    page.screenshot(path=str(png_path), full_page=False)
    browser.close()

print(f'PNG saved: {png_path}')
print('Done!')
