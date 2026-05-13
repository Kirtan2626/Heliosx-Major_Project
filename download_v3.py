import arxiv
import os
import time

papers_dir = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
os.makedirs(papers_dir, exist_ok=True)

# Very targeted queries
queries = [
    'all:"physics-informed" AND all:"solar energy"',
    'all:"reinforcement learning" AND all:"solar tracking"',
    'all:"digital twin" AND all:"solar panel" AND all:"optimization"',
    'all:"reinforcement learning" AND all:"solar fault diagnosis"',
    'all:"physics-informed neural networks" AND all:"photovoltaic"'
]

client = arxiv.Client()
downloaded = 0
# We have 10 left, we need at least 5-10 more to hit the 15-25 range safely.
target_new = 10 

for query in queries:
    search = arxiv.Search(
        query=query,
        max_results=10,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    for result in client.results(search):
        if result.published.year >= 2024:
            safe_title = "".join([c for c in result.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            filename = f"{safe_title[:100]}.pdf"
            filepath = os.path.join(papers_dir, filename)
            
            if not os.path.exists(filepath):
                print(f"Targeted Download: {result.title}")
                try:
                    # Attempt download with higher timeout/retry
                    result.download_pdf(dirpath=papers_dir, filename=filename)
                    # Verify size immediately - if too small, it failed or is meta-data
                    if os.path.getsize(filepath) > 200000:
                        downloaded += 1
                        print(f"Success. Size: {os.path.getsize(filepath)}")
                        time.sleep(3) # Be nice to arXiv
                    else:
                        os.remove(filepath)
                        print("Failed: File too small (likely corrupted/meta).")
                except Exception as e:
                    print(f"Failed: {e}")
                    
            if downloaded >= target_new:
                break
    if downloaded >= target_new:
        break

print(f"Total high-quality papers added: {downloaded}")
