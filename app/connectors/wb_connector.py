import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

import httpx


T = TypeVar("T")


def retry_on_429(
    attempts: int = 3,
    pause_seconds: float = 1.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_response: Any = None
            for attempt in range(attempts):
                response = await func(*args, **kwargs)
                last_response = response
                status_code = getattr(response, "status_code", None)
                if status_code != 429:
                    return response
                if attempt < attempts - 1:
                    await asyncio.sleep(pause_seconds * (attempt + 1))
            return last_response

        return wrapper

    return decorator


class WildberriesClient:
    def __init__(self, token: str, base_url: str = "https://suppliers-api.wildberries.ru"):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry_on_429(attempts=3, pause_seconds=1.0)
    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = await self._client.request(method, path, **kwargs)
        return response

    async def fetch_new_reviews(self, **params) -> httpx.Response:
        return await self.request("GET", "/api/v3/feedbacks", params=params)
