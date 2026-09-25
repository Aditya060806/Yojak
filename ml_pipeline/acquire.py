# ml_pipeline/acquire.py

"""
Fetch every scriptable data source into data/raw/ (see data/SOURCES.md).

    python -m ml_pipeline.acquire            # skip files that already exist
    python -m ml_pipeline.acquire --force    # re-download

ESCO needs a manual download (the portal is form-gated); this script checks for
it and tells you what to do. Kaggle needs ~/.kaggle/kaggle.json.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

from app.core.settings import get_settings

UA = {"User-Agent": "Mozilla/5.0 (Yojak data pipeline)"}
KAGGLE_DATASET = "shivamshrivastava21/indian-job-market-dataset-2025-2026"
NAUKRI_FILE = "indian-job-market-dataset-2025.xlsx"
ESCO_REQUIRED = [
    "occupations_en.csv", "skills_en.csv", "occupationSkillRelations_en.csv", "skillSkillRelations_en.csv",
    "skillsHierarchy_en.csv", "broaderRelationsSkillPillar_en.csv", "skillGroups_en.csv", "ISCOGroups_en.csv",
    "broaderRelationsOccPillar_en.csv", "conceptSchemes_en.csv", "researchOccupationsCollection_en.csv",
    "digitalSkillsCollection_en.csv", "greenSkillsCollection_en.csv", "digCompSkillsCollection_en.csv",
    "researchSkillsCollection_en.csv", "transversalSkillsCollection_en.csv", "languageSkillsCollection_en.csv",
]
DATAMEET = "https://raw.githubusercontent.com/datameet/maps/master/Survey-of-India-Index-Maps/Boundaries/India-States"
DOWNLOADS = [
    ("geonames/IN.zip", "https://download.geonames.org/export/dump/IN.zip"),
    ("geonames/admin1CodesASCII.txt", "https://download.geonames.org/export/dump/admin1CodesASCII.txt"),
    *[(f"boundaries/India-States.{ext}", f"{DATAMEET}.{ext}") for ext in ("shp", "dbf", "shx", "prj")],
    ("govt/ncvet_nco_mapping_2023.pdf",
     "https://ncvet.gov.in/wp-content/uploads/2025/05/Report-on-Mapping-of-Qualifications-with-NCO-Codes.pdf"),
    ("govt/aishe_2021_22.pdf",
     "https://cdnbbsr.s3waas.gov.in/s392049debbe566ca5782a3045cf300a3c/uploads/2024/02/20240719952688509.pdf"),
    # MoSPI serves its PDFs only to requests that come from its own site (Referer check).
    ("govt/AnnualReport_PLFS2023-24L2.pdf",
     "https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf",
     {"Referer": "https://www.mospi.gov.in/"}),
]


def fetch(url: str, dest: Path, force: bool, headers: dict | None = None) -> str:
    if dest.exists() and not force:
        return "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    if dest.suffix == ".pdf" and not dest.read_bytes()[:4] == b"%PDF":
        dest.unlink()
        return "failed (server returned a web page, not a PDF; download it manually)"
    return f"downloaded ({dest.stat().st_size:,} bytes)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    s = get_settings()
    ok = True

    missing = [f for f in ESCO_REQUIRED if not (s.esco_data_dir / f).exists()]
    if missing:
        ok = False
        print(f"ESCO: {len(missing)} of {len(ESCO_REQUIRED)} files missing in {s.esco_data_dir}.")
        print("  Download ESCO v1.2 (English, CSV, classification) from")
        print("  https://esco.ec.europa.eu/en/use-esco/download and unzip it there.")
    else:
        print("ESCO: all 17 files present")

    naukri = s.naukri_data_dir / NAUKRI_FILE
    if naukri.exists() and not args.force:
        print("Naukri: exists")
    else:
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi

            api = KaggleApi()
            api.authenticate()
            api.dataset_download_files(KAGGLE_DATASET, path=str(s.naukri_data_dir), unzip=True)
            print("Naukri: downloaded")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"Naukri: failed ({e}). Put your Kaggle key in ~/.kaggle/kaggle.json.")

    for rel, url, *extra in DOWNLOADS:
        try:
            status = fetch(url, s.external_data_dir / rel, args.force, extra[0] if extra else None)
        except Exception as e:  # noqa: BLE001
            status, ok = f"failed ({e})", False
        print(f"{rel}: {status}")

    gz = s.external_data_dir / "geonames" / "IN.zip"
    if gz.exists() and not (s.external_data_dir / "geonames" / "IN.txt").exists():
        with zipfile.ZipFile(gz) as z:
            z.extractall(gz.parent)
        print("geonames/IN.txt: extracted")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
