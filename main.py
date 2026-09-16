"""
main.py
-------
Root entrypoint for local execution and serverless hosting (e.g. Vercel).
Exposes the FastAPI `app` instance from `src.return_risk.api`.
"""
from src.return_risk.api import app

__all__ = ["app"]
