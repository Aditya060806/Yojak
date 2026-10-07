# Data sources

Raw files live in `data/raw/` and are **not committed**; `.gitignore` excludes them. Run `scripts/run.ps1 data` to fetch the scriptable ones. Each entry lists the URL, retrieval date and licence, plus the first 16 hex characters of the SHA-256 for the file we used. The pipeline reports record full hashes in their provenance block.

| # | Dataset | File(s) | Source | Retrieved | Licence | SHA-256 (prefix) |
|---|---|---|---|---|---|---|
| 1 | ESCO v1.2.x classification, English CSV (17 files used) | `data/raw/esco/*.csv` | <https://esco.ec.europa.eu/en/use-esco/download> (manual, form-gated) | 2026-09-25 | CC BY 4.0 | per file, in report provenance |
| 2 | Indian Job Market Dataset 2025 (Naukri.com postings, ~97.9K rows) | `data/raw/naukri/indian-job-market-dataset-2025.xlsx` | Kaggle `shivamshrivastava21/indian-job-market-dataset-2025-2026` (uploaded 2025-10-14) | 2026-09-25 | CC BY-NC-SA 4.0 | `bbcaaf9bb6846520` |
| 3 | GeoNames India gazetteer | `data/raw/external/geonames/IN.zip` (`IN.txt`) | <https://download.geonames.org/export/dump/IN.zip> | 2026-09-25 | CC BY 4.0 | `e59b47a37200ddd4` |
| 4 | GeoNames admin-1 codes (state names) | `data/raw/external/geonames/admin1CodesASCII.txt` | <https://download.geonames.org/export/dump/admin1CodesASCII.txt> | 2026-09-25 | CC BY 4.0 | `1da92a6323a5fec3` |
| 5 | India state boundaries (Survey of India index map) | `data/raw/external/boundaries/India-States.{shp,dbf,shx,prj}` | <https://github.com/datameet/maps/tree/master/Survey-of-India-Index-Maps/Boundaries> | 2026-09-25 | DataMeet maps repository terms | `f0dbd1126892c41c` (.shp) |
| 6 | AISHE 2021-22 (Ministry of Education) | `data/raw/external/govt/aishe_2021_22.pdf` | <https://cdnbbsr.s3waas.gov.in/s392049debbe566ca5782a3045cf300a3c/uploads/2024/02/20240719952688509.pdf> | 2026-09-25 | Government of India publication | `c4400273cb2d574c` |
| 7 | NCVET Report on Mapping of Qualifications with NCO Codes (22 Aug 2023), basis for NCO-2015 = ISCO-08 at 4-digit Family level | `data/raw/external/govt/ncvet_nco_mapping_2023.pdf` | <https://ncvet.gov.in/wp-content/uploads/2025/05/Report-on-Mapping-of-Qualifications-with-NCO-Codes.pdf> | 2026-09-25 | Government of India publication | `576301bc4b72b971` |
| 7b | NCO-2015 Vol I family list (optional validation) | `data/reference/nco2015_families.csv` (team to transcribe) | <https://www.ncs.gov.in/documents/national%20classification%20of%20occupations%20_vol%20i-%202015.pdf> | not fetched: the server blocks scripted downloads | Government of India publication | |
| 8 | PLFS Annual Report 2023-24 (MoSPI), Table 18: youth (15-29) unemployment rate by state | `data/raw/external/govt/AnnualReport_PLFS2023-24L2.pdf` | <https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf> (MoSPI serves it only with a `Referer: https://www.mospi.gov.in/` header; `acquire.py` sends it) | 2026-09-25 | Government of India publication | `ab4ead2cee181a13` |
| 8b | PLFS 2023-24 press note (cross-check only, not parsed) | `data/raw/external/govt/Press_note_AR_PLFS_2023_24_22092024.pdf` | <https://www.mospi.gov.in/sites/default/files/press_release/Press_note_AR_PLFS_2023_24_22092024.pdf> | 2026-09-25 | Government of India publication | `969e90c48acef4c8` |

## Derived reference tables (`data/reference/`, committed)

| File | How it is made | Source rows |
|---|---|---|
| `city_tiers.csv` | Transcribed from the 7th CPC HRA city classification (X = Tier 1, Y = Tier 2, all other places Tier 3); ambiguous names carry their state. Team to verify against the Ministry of Finance list | MoF Dept of Expenditure O.M. No. 2/5/2014-E.II(B), 21 July 2015, via the list on Wikipedia |
| `city_aliases.csv` | Curated: renamed cities, spellings and localities → canonical city (`lookup` names the GeoNames entry). Team to verify | GeoNames plus common usage |
| `loanwords_hi_pa.csv` | Curated: English workplace terms as written in Devanagari and Gurmukhi → the English term, used by the skill extractor. Team to verify spellings | Common usage |
| `aishe_2021_22_state_outturn.csv` | `ml_pipeline/supply/parse.py`: AISHE Table 33 grand-total out-turn by state (page 186) | #6; West Bengal is unreadable in the PDF and left empty |
| `plfs_2023_24_youth_ur.csv` | `ml_pipeline/supply/parse.py`: PLFS Table 18, age 15-29, usual status (ps+ss), persons (page 133) | #8 |

Each file cites its source in its own header. `data/gold/` holds the frozen stratified samples the team labels; the labels themselves are written there by the labelling tool.
