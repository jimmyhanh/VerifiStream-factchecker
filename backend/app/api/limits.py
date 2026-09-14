from tempfile import SpooledTemporaryFile
from threading import BoundedSemaphore
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send, Message

class UploadLimits:
    """Bound the complete request before multipart parsing, including chunked bodies."""
    def __init__(self, app: ASGIApp, max_bytes: int, slots: int):
        self.app = app
        self.max_bytes = max_bytes
        self.slots = BoundedSemaphore(slots)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") != "/videos":
            await self.app(scope, receive, send)
            return
        if not self.slots.acquire(blocking=False):
            await JSONResponse(
                {"detail": {"code": "busy", "message": "Upload capacity is busy; retry later."}},
                status_code=503, headers={"Retry-After": "5"},
            )(scope, receive, send)
            return
        try:
            # A second bounded spool is intentional: parsers may otherwise accept
            # arbitrarily large file parts before the endpoint starts validation.
            with SpooledTemporaryFile(max_size=1024 * 1024) as body:
                size = 0
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > self.max_bytes:
                        await JSONResponse(
                            {"detail": {"code": "request_too_large", "message": "Request exceeds upload limit."}},
                            status_code=413,
                        )(scope, receive, send)
                        return
                    body.write(chunk)
                    if not message.get("more_body", False):
                        break
                body.seek(0)
                replay_finished = False

                async def replay() -> Message:
                    nonlocal replay_finished
                    if replay_finished:
                        return await receive()
                    chunk = body.read(1024 * 1024)
                    more = body.tell() < size
                    replay_finished = not more
                    return {"type": "http.request", "body": chunk, "more_body": more}

                await self.app(scope, replay, send)
        finally:
            self.slots.release()
