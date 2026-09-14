import asyncio
from app.api.limits import UploadLimits

def test_capacity_rejects_then_releases_slot():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0
        async def endpoint(scope, receive, send):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
        middleware = UploadLimits(endpoint, max_bytes=100, slots=1)
        scope = {"type": "http", "method": "POST", "path": "/videos"}
        async def receive():
            return {"type": "http.request", "body": b"x", "more_body": False}
        messages = []
        async def send(message):
            messages.append(message)
        first = asyncio.create_task(middleware(scope, receive, send))
        await entered.wait()
        await middleware(scope, receive, send)
        assert messages[0]["status"] == 503
        assert calls == 1
        release.set()
        await first
        await middleware(scope, receive, send)
        assert calls == 2
    asyncio.run(scenario())

def test_disconnected_upload_releases_slot():
    async def scenario():
        calls = 0
        async def endpoint(scope, receive, send):
            nonlocal calls
            calls += 1
        middleware = UploadLimits(endpoint, max_bytes=100, slots=1)
        scope = {"type": "http", "method": "POST", "path": "/videos"}
        async def disconnected():
            return {"type": "http.disconnect"}
        async def valid():
            return {"type": "http.request", "body": b"x", "more_body": False}
        async def send(message):
            pass
        await middleware(scope, disconnected, send)
        await middleware(scope, valid, send)
        assert calls == 1
    asyncio.run(scenario())
