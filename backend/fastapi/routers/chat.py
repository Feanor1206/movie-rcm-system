import json
from contextlib import aclosing

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from schemas import ChatRequest, ChatResponse


router = APIRouter()


@router.post("/api/chat", responses={200: {"content": {"text/event-stream": {}}}})
async def chat(request: ChatRequest, http_request: Request):
    query = request.query or ""
    if not query.strip() and request.messages:
        query = request.messages[-1]["content"]
    if not query.strip():
        raise HTTPException(400, "Thiếu trường query hoặc messages.")
    runtime = http_request.app.state.runtime
    snapshot = runtime.snapshot
    if snapshot is None or not snapshot.is_ready:
        raise HTTPException(503, "Chưa có snapshot catalog được chấp nhận.")
    async def events():
        async with aclosing(runtime.chat.stream(query.strip(), history=request.messages,
                                                session_id=request.sessionId, snapshot=snapshot)) as stream:
            async for event, data in stream:
                if await http_request.is_disconnected():
                    break
                if event == "done":
                    data = ChatResponse(**data).model_dump()
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
