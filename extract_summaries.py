import os
import pypdf

dir_path = "C:/Users/kirta/Downloads/KIRTAN - Copy/Research_Papers"
files = [f for f in os.listdir(dir_path) if f.endswith('.pdf')]

with open("paper_summaries.txt", "w", encoding="utf-8") as out:
    for i, f in enumerate(files):
        path = os.path.join(dir_path, f)
        try:
            reader = pypdf.PdfReader(path)
            # Extract first 2 pages for abstract/intro info
            text = ""
            for page in reader.pages[:2]:
                text += page.extract_text() + "\n"
            
            out.write(f"REFERENCE [{i+1}]: {f}\n")
            out.write(f"CONTENT_START:\n{text[:2000]}\nCONTENT_END\n\n")
        except Exception as e:
            out.write(f"ERROR [{i+1}]: {f} - {e}\n")

print("Summaries extracted to paper_summaries.txt")
