# Starts the OneEntry backend on port 8080. Config comes from .env at the
# repo root. Run this in its own terminal (or double-click) and leave it open.
Set-Location "$PSScriptRoot\backend"
python -m uvicorn app.main:app --port 8080
