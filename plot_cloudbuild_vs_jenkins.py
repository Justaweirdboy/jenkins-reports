import matplotlib.pyplot as plt
import numpy as np

builds = ['#908', '#909', '#910', '#911', '#912']
# Jenkins idők (másodpercben)
# #908: 5m 10s = 310s
# #909: 5m 6s = 306s
# #910: 4m 51s = 291s
# #911: 8m 0s = 480s
# #912: 8m 2s = 482s
jenkins_times = [310, 306, 291, 480, 482]

# Cloud Build idők (másodpercben)
# #908 -> 62a29768: 3m 40s = 220s
# #909 -> 9c03818f: 3m 36s = 216s
# #910 -> 741f53e0: 3m 34s = 214s
# #911 -> f3683610: 6m 31s = 391s
# #912 -> 09ff11fe: 6m 33s = 393s
cloudbuild_times = [220, 216, 214, 391, 393]

x = np.arange(len(builds))

fig, ax = plt.subplots(figsize=(10, 6))

ax.plot(x, jenkins_times, marker='o', linestyle='-', linewidth=2, label='Jenkins Build Time', color='#1f77b4')
ax.plot(x, cloudbuild_times, marker='s', linestyle='-', linewidth=2, label='Cloud Build Time', color='#ff7f0e')

for i, txt in enumerate(jenkins_times):
    ax.annotate(f"{txt}s", (x[i], jenkins_times[i]), textcoords="offset points", xytext=(0,10), ha='center', color='#1f77b4', fontweight='bold')

for i, txt in enumerate(cloudbuild_times):
    ax.annotate(f"{txt}s", (x[i], cloudbuild_times[i]), textcoords="offset points", xytext=(0,-15), ha='center', color='#ff7f0e', fontweight='bold')

line_pos = 2.5 
ax.axvline(x=line_pos, color='red', linestyle='--', linewidth=1.5)

ax.text(line_pos - 0.1, max(max(jenkins_times), max(cloudbuild_times)) * 0.9, 
        'remote cache letiltása', color='red', rotation=0, fontweight='bold', ha='right')

ax.set_xticks(x)
ax.set_xticklabels(builds)
ax.set_xlabel('Build Sorszám', fontsize=12, fontweight='bold')
ax.set_ylabel('Időtartam (másodperc)', fontsize=12, fontweight='bold')
ax.set_title('Jenkins vs Cloud Build Idők', fontsize=14, fontweight='bold')
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend()

plt.tight_layout()
plt.show()
