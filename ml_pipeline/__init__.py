"""Yojak data and ML pipelines."""

import os

# PyTorch only: stop `transformers` from importing TensorFlow when it happens to be installed.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
# joblib/loky counts physical cores with `wmic`, which newer Windows builds removed;
# giving it the count directly avoids a noisy (harmless) traceback.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
