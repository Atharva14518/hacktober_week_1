"""Token-protected LAN-only photo upload app; no external network calls."""

from __future__ import annotations

import hmac
import html
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse

from wildquest.vision.images import MAX_UPLOAD_BYTES, normalize_image


async def _read_limited(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    await upload.close()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image exceeds 10 MiB")
    return data


def create_upload_app(directory: Path, token: str) -> FastAPI:
    if len(token) < 16:
        raise ValueError("upload token must contain at least 16 characters")
    app = FastAPI(
        title="Wild Quest local photo upload",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    async def index(token_value: Annotated[str, Query(alias="token")]) -> str:
        if not hmac.compare_digest(token_value, token):
            raise HTTPException(status_code=403, detail="invalid upload token")
        safe_token = html.escape(token, quote=True)
        return f"""<!doctype html>
<html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wild Quest photo</title>
<body><h1>Wild Quest photo</h1>
<p>This stays on the local hotspot and is deleted/replaced by local game setup.</p>
<form action="/upload" method="post" enctype="multipart/form-data">
<input type="hidden" name="token" value="{safe_token}">
<input type="file" name="photo" accept="image/jpeg,image/png,image/webp" capture="environment" required>
<button type="submit">Send photo</button></form></body></html>"""

    @app.post("/upload", status_code=status.HTTP_201_CREATED)
    async def upload(
        photo: Annotated[UploadFile, File()],
        token_value: Annotated[str, Form(alias="token")],
    ) -> dict[str, str]:
        if not hmac.compare_digest(token_value, token):
            raise HTTPException(status_code=403, detail="invalid upload token")
        if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=415, detail="JPEG, PNG, or WebP required")
        data = await _read_limited(photo)
        try:
            path = normalize_image(data, directory)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ready", "image_id": path.name}

    return app
