import sys
from pathlib import Path
from starlette.types import ASGIApp, Receive, Scope, Send

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from return_risk.api import app
from fastapi import Request
from fastapi.responses import JSONResponse

# Diagnostic route to see exactly what Vercel sends
@app.api_route("/api/index.py", methods=["GET", "POST"])
@app.api_route("/api/index", methods=["GET", "POST"])
@app.api_route("/api", methods=["GET", "POST"])
async def vercel_diagnostic(request: Request):
    headers = dict(request.headers)
    matched = headers.get("x-matched-path") or headers.get("x-forwarded-uri")
    return JSONResponse({
        "status": "diagnostic",
        "scope_path": request.scope.get("path"),
        "url_path": request.url.path,
        "matched_path": matched,
        "headers": headers,
    })

class VercelPathMiddleware:
    """Normalizes ASGI scope['path'] when Vercel rewrites requests to /api/index.py."""
    def __init__(self, asgi_app: ASGIApp):
        self.asgi_app = asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")
            if not matched_path:
                matched_path = headers.get(b"x-forwarded-uri", b"").decode("utf-8")
            
            # If Vercel rewrote the path to /api/index.py or /api/index, restore the client's matched path
            if matched_path and matched_path not in ("/api/index.py", "/api/index", "/api"):
                # strip query params if present
                clean_path = matched_path.split("?")[0]
                scope["path"] = clean_path
                
        await self.asgi_app(scope, receive, send)

# Wrap app
app.add_middleware(VercelPathMiddleware)
