from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from battle_school_lunch.config import Settings
from battle_school_lunch.main import create_app


def result(code: str, message: str = "message") -> dict[str, Any]:
    return {"RESULT": {"CODE": code, "MESSAGE": message}}


def page(key: str, rows: list[dict[str, Any]], *, total: int | None = None) -> dict[str, Any]:
    return {
        key: [
            {
                "head": [
                    {"list_total_count": len(rows) if total is None else total},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "success"}},
                ]
            },
            {"row": rows},
        ]
    }


def school_row(
    *,
    office: str = "B10",
    code: str = "7010001",
    name: str = "테스트고등학교",
) -> dict[str, Any]:
    return {
        "ATPT_OFCDC_SC_CODE": office,
        "SD_SCHUL_CODE": code,
        "SCHUL_NM": name,
        "LCTN_SC_NM": "서울특별시",
        "SCHUL_KND_SC_NM": "고등학교",
    }


@pytest.fixture
def app_client() -> Callable[[httpx.MockTransport], Any]:
    @asynccontextmanager
    async def make_client(transport: httpx.MockTransport) -> AsyncIterator[httpx.AsyncClient]:
        neis_http = httpx.AsyncClient(transport=transport, base_url="https://open.neis.go.kr/hub")
        app = create_app(
            settings=Settings(neis_api_key="test-api-key", frontend_origin="http://frontend.test"),
            http_client=neis_http,
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://backend.test",
            ) as client:
                yield client
        await neis_http.aclose()

    return make_client
