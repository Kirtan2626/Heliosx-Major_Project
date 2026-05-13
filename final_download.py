import arxiv
import os
import time

papers_dir = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
client = arxiv.Client()
downloaded = 0

# One broad but relevant query
search = arxiv.Search(
    query='all:"reinforcement learning" AND all:"solar energy"', 
    max_results=20, 
    sort_by=arxiv.SortCriterion.Relevance
)

for result in client.results(search):
    if result.published.year >= 2024:
        safe_title = "".join([c for c in result.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        filename = f"{safe_title[:100]}.pdf"
        filepath = os.path.join(papers_dir, filename)
        if not os.path.exists(filepath):
            try:
                print(f"Trying: {result.title}")
                result.download_pdf(dirpath=papers_dir, filename=filename)
                if os.path.getsize(filepath) > 200000:
                    downloaded += 1
                    print(f"Success. Total new: {downloaded}")
                    time.sleep(15) # Safety delay
                else:
                    os.remove(filepath)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(20) # Back off on 429
    if downloaded >= 8: break

print(f"Finished. Newly added: {downloaded}")
