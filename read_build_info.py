import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import urllib3
import os
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://jenkins.ewiser.hu:42841/view/%20%20%20%20%20merge-requests/job/merge-requests/job/EWT-114_Engine_table_history/wfapi/runs"
USER = os.getenv("JENKINS_USER")
TOKEN = os.getenv("JENKINS_TOKEN_OLD")

url_uj = "http://10.110.0.22:8080/view/%20%20%20%20%20merge-requests/job/merge-requests-gke/view/change-requests/job/MR-5283/wfapi/runs"
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
        row = {
            '_BuildID': build.get('id', 'N/A'),
            '_Total': build.get('durationMillis', 0) / 1000,
            '_Job': job_label
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

df_regi = fetch_job_data(url, USER, TOKEN, "Régi Job")
df_uj = fetch_job_data(url_uj, USER_uj, TOKEN_uj, "Új Job")

if df_regi.empty or df_uj.empty:
    print("\nHIBA: Nem sikerült lekérni az adatokat valamelyik job-ból.")
    exit()

# Kiszűrjük a 4-es buildet mindkét adathalmazból
df_regi = df_regi[df_regi['_BuildID'] != '4'].reset_index(drop=True)
df_uj = df_uj[df_uj['_BuildID'] != '4'].reset_index(drop=True)

print(f"\n4-es build kiszűrve. Régi: {len(df_regi)} build, Új: {len(df_uj)} build")

stage_cols_regi = [col for col in df_regi.columns if not col.startswith('_')]
stage_cols_uj = [col for col in df_uj.columns if not col.startswith('_')]
all_stages_set = set(stage_cols_regi + stage_cols_uj)
PREFERRED_ORDER = ['Checkout', 'Git clone', 'Build', 'Test', 'Declarative: Post Actions']

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
    'Checkout': '#98df8a',
    'Git clone': '#2ca02c',
    'Build': '#1f77b4',
    'Test': '#ff7f0e',
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

regi_ids = df_regi['_BuildID'].head(max_builds).values
uj_ids = df_uj['_BuildID'].head(max_builds).values
xtick_labels = [f"#{r} vs #{u}" for r, u in zip(regi_ids, uj_ids)]

ax.set_xlabel('Build Párok (Régi vs Új)', fontsize=12, fontweight='bold')
ax.set_ylabel('Időtartam (másodperc)', fontsize=12, fontweight='bold')
ax.set_title('Jenkins Pipeline Stage Időtartamok - Régi vs. Új Job', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=45 if max_builds > 8 else 0)
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
print("BUILD-ENKÉNTI RÉSZLETEK:")
print("="*90)
print(f"{'Build (R vs Ú)':<20} {'Régi Total (s)':<18} {'Új Total (s)':<18} {'Különbség':<15} {'%'}")
print("-"*90)
for i in range(max_builds):
    total_regi = df_regi['_Total'].iloc[i]
    total_uj = df_uj['_Total'].iloc[i]
    diff = total_uj - total_regi
    pct = (diff / total_regi * 100) if total_regi > 0 else 0
    
    symbol = "gyorsabb" if diff < 0 else "lassabb" if diff > 0 else "ugyanaz"
    build_label = f"#{regi_ids[i]} vs #{uj_ids[i]}"
    print(f"{build_label:<20} {total_regi:<18.1f} {total_uj:<18.1f} {diff:<15.1f} {pct:+.1f}% ({symbol})")

print("\n" + "="*90)
print("STAGE-ENKÉNTI ÁTLAG IDŐTARTAMOK:")
print("="*90)
print(f"{'Stage':<25} {'Régi Átlag (s)':<20} {'Új Átlag (s)':<20} {'Különbség'}")
print("-"*90)
for stage in all_stages:
    avg_regi = df_regi[stage].head(max_builds).mean()
    avg_uj = df_uj[stage].head(max_builds).mean()
    diff = avg_uj - avg_regi
    print(f"{stage:<25} {avg_regi:<20.2f} {avg_uj:<20.2f} {diff:+.2f}s")

csv_filename = "jenkins_comparison_data.csv"
print(f"\nAdatok mentése CSV-be: {csv_filename}...")

df_regi_export = df_regi.head(max_builds).copy()
df_uj_export = df_uj.head(max_builds).copy()

meta_cols = ['_Job', '_BuildID', '_Total', 'Wait/Other']
stage_cols = [c for c in all_stages if c != 'Wait/Other']
export_cols = meta_cols + stage_cols

final_cols = [c for c in export_cols if c in df_regi_export.columns]

df_export = pd.concat([df_regi_export[final_cols], df_uj_export[final_cols]], ignore_index=True)
df_export.to_csv(csv_filename, index=False, sep=';', decimal=',')
print("✓ Mentés sikeres!")