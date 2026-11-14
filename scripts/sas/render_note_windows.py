"""Export the saved DOCX with Word's file API and rasterize every PDF page."""

import json
import site
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
site.addsitedir(str(ROOT / "private_sas/doc_deps"))
import pymupdf  # noqa: E402
import win32com.client  # noqa: E402

out = ROOT / "private_sas/submission"
source = out / "Yojak_Approach_Note.docx"
target = out / "Yojak_Approach_Note.pdf"
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
document = None
try:
    document = word.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)
    document.Repaginate()
    document.ExportAsFixedFormat(str(target), 17)
finally:
    if document is not None:
        document.Close(False)
    word.Quit()

pdf = pymupdf.open(target)
render = out / "review_v4"
render.mkdir(exist_ok=True)
pages = []
for i, page in enumerate(pdf):
    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(render / f"page-{i + 1:02}.png")
    pages.append({"page": i + 1, "words": len(page.get_text().split()), "text": page.get_text()})
(render / "pages.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
print(f"Exported {len(pdf)} pages to {target}")
if len(pdf) > 26:
    raise SystemExit("Page limit exceeded; revise layout before delivery")
