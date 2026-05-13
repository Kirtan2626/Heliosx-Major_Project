import arxiv
import os
import datetime

# Create directory
papers_dir = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
os.makedirs(papers_dir, exist_ok=True)

queries = [
    'all:"solar energy" AND all:"reinforcement learning"',
    'all:"solar panel" AND all:"deep learning"',
    'all:"digital twin" AND all:"solar"',
    'all:"photovoltaic" AND all:"optimization"',
]

downloaded = 0
client = arxiv.Client()

for query in queries:
    search = arxiv.Search(
        query=query,
        max_results=10,
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
                    result.download_pdf(dirpath=papers_dir, filename=filename)
                    downloaded += 1
                except Exception as e:
                    print(f"Failed to download {result.title}: {e}")
                    
            if downloaded >= 18:
                break
    if downloaded >= 18:
        break

print(f"Total downloaded: {downloaded}")
