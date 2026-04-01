"""
EchoHound File Reader
Extracts text from documents sent to the bot.
Supports: PDF, TXT, CSV, MD, DOCX
"""

import io
from pathlib import Path

MAX_FILE_CHARS = 20_000

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _read_pdf(file_bytes)
    elif ext == ".docx":
        return _read_docx(file_bytes)
    elif ext in (".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".xml"):
        return _read_plain(file_bytes)
    else:
        return f"[Unsupported file type: {ext}. Supported: pdf, docx, txt, md, csv, json, py, js, ts, html, xml]"

def _read_plain(data: bytes) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    return _truncate(text)

def _read_pdf(data: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = [page.extract_text().strip() for page in reader.pages if page.extract_text()]
        return _truncate("\n\n".join(pages)) if pages else "[PDF had no extractable text]"
    except ImportError:
        return "[pypdf not installed — run: pip install pypdf]"
    except Exception as e:
        return f"[PDF read error: {e}]"

def _read_docx(data: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return _truncate(text) if text else "[DOCX had no extractable text]"
    except ImportError:
        return "[python-docx not installed — run: pip install python-docx]"
    except Exception as e:
        return f"[DOCX read error: {e}]"

def _truncate(text: str) -> str:
    if len(text) <= MAX_FILE_CHARS:
        return text
    return text[:MAX_FILE_CHARS] + f"\n\n[...truncated — {len(text):,} chars total, showing first {MAX_FILE_CHARS:,}]"
