import arxiv
import os
import time
import urllib.request

papers_dir = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
os.makedirs(papers_dir, exist_ok=True)

queries = [
    'all:"solar power" AND all:"reinforcement learning"',
    'all:"solar forecasting" AND all:"deep learning"',
    'all:"photovoltaic system" AND all:"simulation"',
]

client = arxiv.Client()
downloaded = 0
target = 5

for query in queries:
    search = arxiv.Search(
        query=query,
        max_results=15,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    for result in client.results(search):
        if result.published.year >= 2024 and result.published.year <= 2026:
            safe_title = "".join([c for c in result.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            filename = f"{safe_title[:100]}.pdf"
            filepath = os.path.join(papers_dir, filename)
            
            if not os.path.exists(filepath):
                print(f"Downloading: {result.title}")
                try:
                    # Retry logic
                    for _ in range(3):
                        try:
                            result.download_pdf(dirpath=papers_dir, filename=filename)
                            downloaded += 1
                            time.sleep(2)
                            break
                        except Exception as e:
                            print(f"Retry after error: {e}")
                            time.sleep(5)
                except Exception as e:
                    print(f"Failed to download {result.title}: {e}")
                    
            if downloaded >= target:
                break
    if downloaded >= target:
        break

print(f"Total newly downloaded: {downloaded}")
