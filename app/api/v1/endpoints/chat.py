"""Chat completion endpoints (thin HTTP layer).

Depend only on the vendor-neutral ``LLMProvider`` interface via the
``get_llm`` dependency — never on a concrete provider. Business logic
lives in ``app.services.llm.service``.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.llm import ChatRequest, ChatResponse
from app.services.llm import (
    LLMConfigError,
    LLMError,
    LLMProvider,
    get_llm,
    get_llm_provider,
)
from app.services.llm import service as llm_service

router = APIRouter(tags=["llm"])


def _status_for(exc: LLMError) -> int:
    return 500 if isinstance(exc, LLMConfigError) else 502


def _resolve(body: ChatRequest, provider: LLMProvider) -> LLMProvider:
    if body.provider:
        return get_llm_provider(body.provider)
    return provider


@router.post("/chat", response_model=ChatResponse, summary="Chat completion")
async def chat(
    body: ChatRequest,
    provider: LLMProvider = Depends(get_llm),
) -> ChatResponse:
    try:
        active = _resolve(body, provider)
        result = await llm_service.achat(
            body.messages,
            active,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except LLMError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc
    usage = result.usage
    return ChatResponse(
        content=result.content,
        model=result.model,
        provider=result.provider,
        finish_reason=result.finish_reason,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
        latency_ms=usage.latency_ms if usage else None,
    )


@router.post("/chat/stream", summary="Chat completion (SSE stream)")
async def chat_stream(
    body: ChatRequest,
    provider: LLMProvider = Depends(get_llm),
) -> StreamingResponse:
    """Stream ``data: <StreamChunk JSON>`` events, terminated by ``data: [DONE]``.

    Consume from the frontend with ``fetch`` + ``ReadableStream`` (EventSource
    cannot POST). Mid-stream failures arrive as ``data: {"error": "..."}``
    followed by ``[DONE]``; dependency failures (missing key, bad provider)
    return a regular JSON error via the app's ``LLMError`` handler.
    """
    try:
        active = _resolve(body, provider)
    except LLMError as exc:
        raise HTTPException(status_code=_status_for(exc), detail=str(exc)) from exc

    async def event_gen():
        try:
            async for chunk in llm_service.astream(
                body.messages,
                active,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                yield f"data: {chunk.model_dump_json()}\n\n"
        except LLMError as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
