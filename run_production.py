"""
Production entry point (Waitress WSGI server).

Usage:
  .venv\\Scripts\\python run_production.py

Environment (optional, in .env):
  APP_HOST=0.0.0.0
  APP_PORT=5000
  APP_THREADS=4
"""

import os

import env_loader  # noqa: F401 - loads .env from project root
from waitress import serve

from app import app

HOST = (os.getenv("APP_HOST") or "0.0.0.0").strip()
PORT = int((os.getenv("APP_PORT") or "5000").strip())
THREADS = int((os.getenv("APP_THREADS") or "4").strip())

if __name__ == "__main__":
    print(f"User Disabling Platform listening on http://{HOST}:{PORT}")
    serve(app, host=HOST, port=PORT, threads=THREADS)
