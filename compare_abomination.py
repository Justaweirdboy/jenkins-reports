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

url_regi = "https://jenkins.ewiser.hu:42841/view/%20%20test-environments/job/test-environments/job/abomination-core/job/build-image/wfapi/runs"
USER_regi = os.getenv("JENKINS_USER")
TOKEN_regi = os.getenv("JENKINS_TOKEN_OLD")

url_uj = "http://10.110.0.22:8080/view/%20%20test-environments/job/test-environments/job/abomination-core/job/build-image/wfapi/runs"
USER_uj = os.getenv("JENKINS_USER")
TOKEN_uj = os.getenv("JENKINS_TOKEN_NEW")

def fetch_job_data(url, user, token, job_label):
    print(f"\nAdatok lekérése: {job_label}...")
    try:
        response = requests.get(url, auth=(user, token), verify=False).json()
    except Exception as e:
        print(f"HIBA az adatok lekérésekor: {e}")
        return pd.DataFrame()
    
    data_list = []
    for build in response:
        timestamp_ms = build.get('startTimeMillis', 0)
        if timestamp_ms:
            dt_object = datetime.fromtimestamp(timestamp_ms / 1000)
            time_str = dt_object.strftime('%Y-%m-%d\n%H:%M')
        else:
            time_str = "N/A"

        row = {
            '_BuildID': build.get('id', 'N/A'),
            '_Total': build.get('durationMillis', 0) / 1000,
            '_Job': job_label,
            '_Time': time_str
        }
        
        for stage in build.get('stages', []):
            stage_name = stage['name']
            duration_sec = stage['durationMillis'] / 1000
            row[stage_name] = duration_sec
            
        data_list.append(row)
    
    df = pd.DataFrame(data_list)
    
    if not df.empty:
        df = df.iloc[::-1].reset_index(drop=True)
        df = df.fillna(0)
    
    print(f"  {len(df)} build lekérve")
    return df

df_regi = fetch_job_data(url_regi, USER_regi, TOKEN_regi, "Régi Job")
df_uj = fetch_job_data(url_uj, USER_uj, TOKEN_uj, "Új Job")

if df_regi.empty or df_uj.empty:
    print("\nHIBA: Nem sikerült lekérni az adatokat valamelyik job-ból.")
    exit()

df_regi = df_regi.tail(5).reset_index(drop=True)
df_uj = df_uj.tail(5).reset_index(drop=True)

print(f"\nElemzésre kiválasztva: utolsó {len(df_regi)} build")

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
print(f"\nStage sorrend: {all_stages}")

for stage in all_stages:
    if stage not in df_regi.columns:
        df_regi[stage] = 0
    if stage not in df_uj.columns:
        df_uj[stage] = 0

max_builds = min(len(df_regi), len(df_uj))
print(f"\n✓ {max_builds} build párosítható (index alapján)")

x = np.arange(max_builds)
width = 0.4

fig, ax = plt.subplots(figsize=(16, 8))

color_map = {
    'Wait/Other': '#d3d3d3',
    'Init': '#c7c7c7',
    'Declarative: Checkout SCM': '#98df8a',
    'Git clone': '#2ca02c',
    'Checkout': '#2ca02c',
    'Build': '#1f77b4',
    'Build & Push (Google Cloud Build)': '#1f77b4',
    'Push image': '#aec7e8',
    'Declarative: Post Actions': '#9467bd'
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
    values = df_regi[stage].head(max_builds).values
    ax.bar(x - width/2, values, width, bottom=bottom_regi, 
           label=f'{stage}' if idx == 0 else '', 
           color=stage_colors[idx], alpha=0.9, edgecolor='white', linewidth=0.5)
    bottom_regi += values

bottom_uj = np.zeros(max_builds)
for idx, stage in enumerate(all_stages):
    values = df_uj[stage].head(max_builds).values
    ax.bar(x + width/2, values, width, bottom=bottom_uj,
           label='', 
           color=stage_colors[idx], alpha=0.9, edgecolor='white', linewidth=0.5)
    bottom_uj += values

for i in range(max_builds):
    total_regi = df_regi['_Total'].iloc[i]
    total_uj = df_uj['_Total'].iloc[i]
    
    ax.text(x[i] - width/2, total_regi, f'{total_regi:.0f}s', 
            ha='center', va='bottom', fontsize=9, fontweight='bold', color='black')
    
    ax.text(x[i] + width/2, total_uj, f'{total_uj:.0f}s', 
            ha='center', va='bottom', fontsize=9, fontweight='bold', color='black')

regi_times = df_regi['_Time'].head(max_builds).values
uj_times = df_uj['_Time'].head(max_builds).values
xtick_labels = [f"R: {r}\nÚ: {u}" for r, u in zip(regi_times, uj_times)]

ax.set_xlabel('Build Időpontok (Régi vs Új)', fontsize=12, fontweight='bold')
ax.set_ylabel('Időtartam (másodperc)', fontsize=12, fontweight='bold')
ax.set_title('Jenkins Pipeline Stage Időtartamok - Abomination Core', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=0, fontsize=9)
ax.grid(axis='y', linestyle='--', alpha=0.5)

handles = []
labels = []
for idx, stage in enumerate(all_stages):
    handles.append(plt.Rectangle((0,0),1,1, fc=stage_colors[idx], alpha=0.9))
    labels.append(stage)

ax.legend(handles, labels, title='Stages', loc='upper left', bbox_to_anchor=(1, 1), fontsize=10)

plt.tight_layout()
plt.show()

print("\n" + "="*90)
print("BUILD-ENKÉNTI RÉSZLETEK (UTOLSÓ 5):")
print("="*90)
print(f"{'Build (R vs Ú)':<20} {'Régi Total (s)':<18} {'Új Total (s)':<18} {'Különbség':<15} {'%'}")
print("-"*90)
for i in range(max_builds):
    total_regi = df_regi['_Total'].iloc[i]
    total_uj = df_uj['_Total'].iloc[i]
    diff = total_uj - total_regi
    pct = (diff / total_regi * 100) if total_regi > 0 else 0
    
    symbol = "gyorsabb" if diff < 0 else "lassabb" if diff > 0 else "ugyanaz"
    build_label = f"#{df_regi['_BuildID'].iloc[i]} vs #{df_uj['_BuildID'].iloc[i]}"
    print(f"{build_label:<20} {total_regi:<18.1f} {total_uj:<18.1f} {diff:<15.1f} {pct:+.1f}% ({symbol})")