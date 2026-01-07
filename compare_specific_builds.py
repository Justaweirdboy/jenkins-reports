import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import urllib3
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url_regi_base = "https://jenkins.ewiser.hu:42841/view/%20%20test-environments/job/test-environments/job/abomination-core/job/build-image"
USER_regi = os.getenv("JENKINS_USER")
TOKEN_regi = os.getenv("JENKINS_TOKEN_OLD")

url_uj_base = "http://10.110.0.22:8080/view/%20%20test-environments/job/test-environments/job/abomination-core/job/build-image"
USER_uj = os.getenv("JENKINS_USER")
TOKEN_uj = os.getenv("JENKINS_TOKEN_NEW")

BUILD_PAIRS = [
    (823, 908),
    (826, 909),
    (832, 910)
]

def fetch_single_build(base_url, build_id, user, token, job_label):
    url = f"{base_url}/{build_id}/wfapi/describe"
    print(f"Lekérés: {job_label} #{build_id}...")
    try:
        response = requests.get(url, auth=(user, token), verify=False)
        if response.status_code != 200:
            print(f"  HIBA: {response.status_code} - {url}")
            return None
        return response.json()
    except Exception as e:
        print(f"  KIVÉTEL: {e}")
        return None

def process_build_data(build_data, job_label):
    if not build_data:
        return None

    timestamp_ms = build_data.get('startTimeMillis', 0)
    if timestamp_ms:
        dt_object = datetime.fromtimestamp(timestamp_ms / 1000)
        time_str = dt_object.strftime('%Y-%m-%d\n%H:%M')
    else:
        time_str = "N/A"

    row = {
        '_BuildID': build_data.get('id', 'N/A'),
        '_Total': build_data.get('durationMillis', 0) / 1000,
        '_Job': job_label,
        '_Time': time_str
    }
    
    for stage in build_data.get('stages', []):
        stage_name = stage['name']
        duration_sec = stage['durationMillis'] / 1000
        row[stage_name] = duration_sec
        
    return row

data_regi = []
data_uj = []

print("\n--- Adatok gyűjtése ---")
for r_id, u_id in BUILD_PAIRS:
    raw_r = fetch_single_build(url_regi_base, r_id, USER_regi, TOKEN_regi, "Régi")
    if raw_r:
        data_regi.append(process_build_data(raw_r, "Régi Job"))
    
    raw_u = fetch_single_build(url_uj_base, u_id, USER_uj, TOKEN_uj, "Új")
    if raw_u:
        data_uj.append(process_build_data(raw_u, "Új Job"))

df_regi = pd.DataFrame(data_regi).fillna(0)
df_uj = pd.DataFrame(data_uj).fillna(0)

if df_regi.empty or df_uj.empty:
    print("\nHIBA: Nem sikerült elegendő adatot lekérni.")
    exit()

print(f"\nSikeresen feldolgozva: {len(df_regi)} pár build")

stage_cols_regi = [col for col in df_regi.columns if not col.startswith('_')]
stage_cols_uj = [col for col in df_uj.columns if not col.startswith('_')]
all_stages_set = set(stage_cols_regi + stage_cols_uj)

PREFERRED_ORDER = [
    'Wait/Other',
    'Init', 
    'Declarative: Checkout SCM', 
    'Git clone', 
    'Checkout', 
    'Build', 
    'Build & Push (Google Cloud Build)', 
    'Push image', 
    'Declarative: Post Actions'
]

sorted_stages = []
for stage in PREFERRED_ORDER:
    if stage in all_stages_set:
        sorted_stages.append(stage)
        all_stages_set.remove(stage)

sorted_stages.extend(sorted(list(all_stages_set)))

existing_stages_regi = [s for s in sorted_stages if s in df_regi.columns]
existing_stages_uj = [s for s in sorted_stages if s in df_uj.columns]

df_regi['_StageSum'] = df_regi[existing_stages_regi].sum(axis=1)
df_uj['_StageSum'] = df_uj[existing_stages_uj].sum(axis=1)

df_regi['Wait/Other'] = df_regi['_Total'] - df_regi['_StageSum']
df_uj['Wait/Other'] = df_uj['_Total'] - df_uj['_StageSum']

df_regi['Wait/Other'] = df_regi['Wait/Other'].apply(lambda x: max(0, x))
df_uj['Wait/Other'] = df_uj['Wait/Other'].apply(lambda x: max(0, x))

if 'Wait/Other' not in sorted_stages:
    sorted_stages.insert(0, 'Wait/Other')

all_stages = sorted_stages

for stage in all_stages:
    if stage not in df_regi.columns:
        df_regi[stage] = 0
    if stage not in df_uj.columns:
        df_uj[stage] = 0

max_builds = len(df_regi)
x = np.arange(max_builds)
width = 0.4

fig, ax = plt.subplots(figsize=(12, 6))

color_map = {
    'Wait/Other': '#BDBDBD',           # Szürke
    'Init': '#795548',                  # Barna
    'Declarative: Checkout SCM': '#4CAF50',  # Zöld
    'Git clone': '#FF9800',             # Narancs
    'Checkout': '#CDDC39',              # Lime/sárgazöld
    'Build': '#2196F3',                 # Kék
    'Build & Push (Google Cloud Build)': '#E91E63',  # Pink/magenta
    'Push image': '#00BCD4',            # Cyan/türkiz
    'Declarative: Post Actions': '#9C27B0'  # Lila
}

default_colors = plt.cm.tab20(np.linspace(0, 1, len(all_stages)))
stage_colors = []
for i, stage in enumerate(all_stages):
    if stage in color_map:
        stage_colors.append(color_map[stage])
    else:
        stage_colors.append(default_colors[i])

bottom_regi = np.zeros(max_builds)
for idx, stage in enumerate(all_stages):
    values = df_regi[stage].values
    ax.bar(x - width/2, values, width, bottom=bottom_regi, 
           color=stage_colors[idx], alpha=0.9, edgecolor='white', linewidth=0.5)
    bottom_regi += values

bottom_uj = np.zeros(max_builds)
for idx, stage in enumerate(all_stages):
    values = df_uj[stage].values
    ax.bar(x + width/2, values, width, bottom=bottom_uj,
           color=stage_colors[idx], alpha=0.9, edgecolor='white', linewidth=0.5)
    bottom_uj += values

for i in range(max_builds):
    ax.text(x[i] - width/2, df_regi['_Total'].iloc[i], f"{df_regi['_Total'].iloc[i]:.0f}s", 
            ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(x[i] + width/2, df_uj['_Total'].iloc[i], f"{df_uj['_Total'].iloc[i]:.0f}s", 
            ha='center', va='bottom', fontsize=9, fontweight='bold')

regi_ids = df_regi['_BuildID'].values
uj_ids = df_uj['_BuildID'].values

xtick_labels = [f"#{rid} vs #{uid}" for rid, uid in zip(regi_ids, uj_ids)]

ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=0, fontsize=10)
ax.set_ylabel('Időtartam (másodperc)', fontweight='bold')
ax.set_title('Image buildek sebességének összehasonlítása a régi és az új Jenkins esetén', fontweight='bold')
ax.grid(axis='y', linestyle='--', alpha=0.5)

handles = [plt.Rectangle((0,0),1,1, fc=c) for c in stage_colors]
ax.legend(handles, all_stages, title='Stages', loc='upper left', bbox_to_anchor=(1, 1))

plt.tight_layout()
plt.show()

csv_filename = "jenkins_specific_comparison.csv"
print(f"\nAdatok mentése CSV-be: {csv_filename}...")

meta_cols = ['_Job', '_BuildID', '_Total', '_Time', 'Wait/Other']
stage_cols_export = [c for c in all_stages if c != 'Wait/Other']
export_cols = meta_cols + stage_cols_export

final_cols = [c for c in export_cols if c in df_regi.columns]

df_export = pd.concat([df_regi[final_cols], df_uj[final_cols]], ignore_index=True)
df_export.to_csv(csv_filename, index=False, sep=';', decimal=',')
print("✓ Mentés sikeres!")
