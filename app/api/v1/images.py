"""Own images: served to anyone who has the (random) name, added by logged-in users."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.images import (
    MAX_IMAGE_BYTES,
    MEDIA_TYPES,
    ImageError,
    fetch_image,
    image_file,
    save_image,
)

router = APIRouter()


class ImageUrlBody(BaseModel):
    url: str


@router.get("/{name}")
async def get_image(name: str) -> FileResponse:
    """No login: next/image's optimizer fetches it without the user's cookie."""
    path = image_file(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[path.suffix[1:]],
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("", dependencies=[Depends(get_current_user)])
async def upload_image(file: UploadFile) -> dict:
    """An image from the PC; returns its "local:<name>" path."""
    data = await file.read(MAX_IMAGE_BYTES + 1)
    try:
        return {"path": save_image(data)}
    except ImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/from-url", dependencies=[Depends(get_current_user)])
async def image_from_url(body: ImageUrlBody) -> dict:
    """A pasted link, downloaded and kept: it keeps working if the site drops it."""
    try:
        return {"path": save_image(await fetch_image(body.url))}
    except ImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
