
from pypdf import PdfReader

def read_resume(path="private/resume.pdf"):
    reader = PdfReader(path)

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    return text.strip()

if __name__ == "__main__":
    resume = read_resume()
    print(resume[:1500])
