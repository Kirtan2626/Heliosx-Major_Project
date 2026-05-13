import requests
import os
import time

# Targeted Research Papers list from arXiv and Nature (Confirmed accessible via simple requests)
papers = [
    {
        "url": "https://arxiv.org/pdf/2401.15853.pdf",
        "title": "Attentive Convolutional Deep RL for Optimizing Solar-Storage Systems.pdf"
    },
    {
        "url": "https://arxiv.org/pdf/2411.15422.pdf",
        "title": "Learning a Local Trading Strategy DRL for Grid-Scale Renewable Energy.pdf"
    },
    {
        "url": "https://arxiv.org/pdf/2403.07846.pdf",
        "title": "Improving Fairness in PV Curtailments via Daily Topology Reconfiguration RL.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41598-024-69544-8.pdf",
        "title": "Enhancing solar PV energy production prediction ML models tuned with chimp optimization.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41467-024-45670-9.pdf",
        "title": "Instrument-To-Instrument translation restoration of solar observation via deep learning.pdf"
    },
    {
        "url": "https://arxiv.org/pdf/2304.05436.pdf", # Near 2024, high relevance
        "title": "MIP-DQN Constraint-Aware RL for Optimal Energy System Scheduling.pdf"
    },
    {
        "url": "https://arxiv.org/pdf/2406.18423.pdf",
        "title": "HIRO-MADDPG for Green Electricity Quota Optimization.pdf"
    },
    {
        "url": "https://arxiv.org/pdf/2405.01234.pdf",
        "title": "Physics-Informed Digital Twin for PV Fault Diagnosis.pdf"
    }
]

dir_path = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
os.makedirs(dir_path, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

count = 0
for paper in papers:
    save_path = os.path.join(dir_path, paper["title"])
    if not os.path.exists(save_path):
        print(f"Downloading: {paper['title']}")
        try:
            response = requests.get(paper["url"], headers=headers, stream=True, timeout=30)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                if os.path.getsize(save_path) > 100000:
                    print(f"Success: {paper['title']}")
                    count += 1
                else:
                    os.remove(save_path)
                    print(f"Failed (Small file): {paper['title']}")
            else:
                print(f"Failed (HTTP {response.status_code}): {paper['title']}")
            
            time.sleep(10) # Heavy delay for arXiv
        except Exception as e:
            print(f"Error: {e}")

print(f"Phase 2 Finished. Downloaded {count} new high-quality papers.")
