import requests
import os
import time

# Targeted Research Papers similar to the COMLAT (Nature 2025) paper
papers = [
    {
        "url": "https://www.mdpi.com/1996-1073/18/7/1724/pdf",
        "title": "Reinforcement Learning for Optimizing Renewable Energy Utilization in Buildings 2025.pdf"
    },
    {
        "url": "https://www.mdpi.com/1424-8220/25/19/6242/pdf",
        "title": "PINN-DT Optimizing Energy Consumption Using Hybrid Physics-Informed NN and Digital Twin 2025.pdf"
    },
    {
        "url": "https://www.nature.com/articles/s41467-025-57292-w.pdf",
        "title": "Global spatiotemporal optimization of photovoltaic and wind power 2025.pdf"
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
            # Note: MDPI sometimes blocks simple requests, adding high delay and better headers
            response = requests.get(paper["url"], headers=headers, stream=True, timeout=30)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                if os.path.getsize(save_path) > 200000:
                    print(f"Successfully downloaded {paper['title']}")
                    count += 1
                else:
                    os.remove(save_path)
                    print(f"Failed: File too small for {paper['title']}")
            else:
                print(f"Failed: HTTP {response.status_code} for {paper['title']}")
            
            time.sleep(5) 
        except Exception as e:
            print(f"Error downloading {paper['title']}: {e}")

print(f"Finished. Downloaded {count} highly relevant papers.")
