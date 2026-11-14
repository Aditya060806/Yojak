"""Generate private, reproducible SAS exchange tables without uploading them."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .data import ROOT, write_json


def export_bundle(out: Path):
    manifest = json.loads((out / "manifest.json").read_text())
    bundle = out / "sas_bundle"
    bundle.mkdir(exist_ok=True)
    for name in ["analytics", "company", "jds", "sds"]:
        frame = pd.read_parquet(out / f"{name}.parquet")
        if name == "analytics":
            frame["skill_count"] = frame.skills.map(len)
            frame["statistics"] = frame.skills.map(lambda s: int(any("stat" in x for x in s)))
            frame["modelling"] = frame.skills.map(lambda s: int(any("model" in x for x in s)))
            frame = frame[["row_key", "group_id", "split", "band", "exp_min", "exp_max", "exp_mid", "skill_count",
                           "statistics", "modelling", "skills_truncated", "quality_flag", "multiplicity"]].copy()
            for flag in ["skills_truncated", "quality_flag"]:
                frame[flag] = frame[flag].astype(int)
        elif name == "company":
            frame["log_pay"] = np.log(frame.avg_salary_native)
            frame["experience_value"] = frame.min_experience
        else:
            frame = frame.rename(columns={manifest["audit"][name]["target"]: "target", "maths-stats_skills": "maths_stats_skills"})
        frame.to_csv(bundle / f"{name}_sas.csv", index=False)
    shutil.copyfile(ROOT / "scripts/sas/validate.sas", bundle / "validate.sas")
    write_json(bundle / "manifest.json", {"source_version": manifest["source_version"], "status": "not executed",
                                         "authorization": "Organizer-approved tenant only; verify transfer permission first",
                                         "partition_mapping": "train / validation / calibration / test; never train on calibration"})
