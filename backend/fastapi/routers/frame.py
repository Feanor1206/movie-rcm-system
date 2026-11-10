from fastapi import APIRouter, Depends, HTTPException, Request


router = APIRouter()
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def read_image(http_request: Request):
    if http_request.headers.get("content-type", "").split(";")[0] not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.")
    image = bytearray()
    async for chunk in http_request.stream():
        image.extend(chunk)
        if len(image) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Ảnh vượt quá 5 MiB.")
    if not image:
        raise HTTPException(400, "Ảnh trống.")
    if not (image.startswith(b"\xff\xd8\xff") or image.startswith(b"\x89PNG\r\n\x1a\n")
            or (image.startswith(b"RIFF") and image[8:12] == b"WEBP")):
        raise HTTPException(415, "Dữ liệu ảnh không hợp lệ.")
    return bytes(image)


@router.post("/v1/frame-search")
def frame_search(http_request: Request, image: bytes = Depends(read_image)):
    runtime = http_request.app.state.runtime
    service = runtime.registry.get("frame_search")
    if service is None or runtime.snapshot is None:
        raise HTTPException(503, "Chưa có model và chỉ mục frame.")
    with runtime.registry.gpu_slot():
        return {"results": service.search(image)}
