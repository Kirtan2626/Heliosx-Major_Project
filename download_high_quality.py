import requests
import os
import time

# Targeted Research Papers list from MDPI, Nature, etc.
papers = [
    {
        "url": "https://www.mdpi.com/1996-1073/18/7/1724/pdf",
        "title": "RL for Optimizing Renewable Energy Utilization in Buildings A Review.pdf"
    },
    {
        "url": "https://www.mdpi.com/1996-1073/17/24/6420/pdf",
        "title": "Applications of Deep RL for Home Energy Management Systems A Review.pdf"
    },
    {
        "url": "https://www.mdpi.com/2077-1312/12/5/762/pdf",
        "title": "Deep RL-Based Optimization for a Green Ship Energy Management System.pdf"
    },
    {
        "url": "https://www.mdpi.com/1996-1073/17/1/231/pdf",
        "title": "Comparative Performance Evaluation of ML-Based Control Strategies for Microgrids.pdf"
    },
    {
        "url": "https://www.mdpi.com/1996-1073/17/11/2659/pdf",
        "title": "RL for Energy Management in Energy Communities A Comparative Study.pdf"
    },
    {
        "url": "https://www.mdpi.com/1424-8220/25/19/6242/pdf",
        "title": "PINN-DT Optimizing Energy Consumption in Smart Building Using Hybrid PINN and Digital Twin.pdf"
    },
    {
        "url": "https://www.mdpi.com/1424-8220/24/22/7145/pdf",
        "title": "A Physics-Informed Digital Twin for Steady-State Thermal Fields in PV.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41598-024-69544-8.pdf",
        "title": "Enhancing solar PV energy production prediction using diverse ML models tuned with chimp optimization.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41467-025-57292-w.pdf",
        "title": "Global spatiotemporal optimization of PV and wind power to achieve the Paris Agreement targets.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41467-024-45670-9.pdf",
        "title": "Instrument-To-Instrument translation drive restoration of solar observation series via deep learning.pdf"
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
                
                # Check file size to ensure it's a real PDF (usually > 500KB)
                if os.path.getsize(save_path) > 100000:
                    print(f"Successfully downloaded {paper['title']}")
                    count += 1
                else:
                    os.remove(save_path)
                    print(f"Failed: File too small (likely meta-page) for {paper['title']}")
            else:
                print(f"Failed: HTTP {response.status_code} for {paper['title']}")
            
            time.sleep(2) # Be polite
        except Exception as e:
            print(f"Error downloading {paper['title']}: {e}")

print(f"Finished. Downloaded {count} new high-quality papers.")
