"""Independent informational provider demo: no DB, wallet, orders or payments."""

from html import escape
from typing import Annotated

from fastapi import FastAPI, Path
from fastapi.responses import HTMLResponse

app = FastAPI(title="Demo Provider", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/assets/{symbol}", response_class=HTMLResponse)
async def asset(symbol: Annotated[str, Path(min_length=1, max_length=64)]):
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo Provider</title>
<style>body{background:#040a1b;color:#f7f8fc;font:18px system-ui;margin:0;padding:32px}
main{max-width:640px;margin:10vh auto}h1{color:#35dcec}p{line-height:1.6}</style></head>
<body><main><p>External provider demo</p><h1>"""
        + escape(symbol)
        + """</h1>
<p>You have left the YUDY app and opened a separate demo provider.</p>
<p>This is an informational demo. Purchases, orders, deposits and payments are unavailable.
No transaction has been performed.</p>
<p>Return to YUDY using your browser or device Back control.</p>
</main></body></html>""",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
