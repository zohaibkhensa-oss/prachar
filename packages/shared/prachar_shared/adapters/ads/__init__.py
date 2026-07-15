from __future__ import annotations

# Adapters register themselves at their own module import time.
# Do NOT eagerly import here — it causes circular imports with registry.py.
# Import adapter modules explicitly where needed:
#   from prachar_shared.adapters.ads.google_ads import GoogleAdsAdapter
