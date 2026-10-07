"""
main.py
-------
Root entrypoint for local execution and serverless hosting (e.g. Vercel).
Exposes the FastAPI `app` instance from `src.return_risk.api`.
"""
from src.return_risk.api import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
