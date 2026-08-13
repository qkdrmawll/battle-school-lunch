from urllib.parse import parse_qs

import httpx
import pytest

from battle_school_lunch.clients.neis import LUNCH_CODE, NeisClient
from battle_school_lunch.errors import UpstreamError, UpstreamUnavailableError

from conftest import page, result, school_row


@pytest.mark.asyncio
async def test_school_search_paginates_using_total_count() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page_index = parse_qs(request.url.query.decode())["pIndex"][0]
        rows = [school_row(code=f"code-{page_index}")]
        return httpx.Response(200, json=page("schoolInfo", rows, total=101))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://open.neis.go.kr/hub")
    client = NeisClient("secret", http_client=http)
    rows = await client.search_schools("고등학교")
    await http.aclose()

    assert len(requests) == 2
    assert [row.school_code for row in rows] == ["code-1", "code-2"]
    query = parse_qs(requests[0].url.query.decode())
    assert query["Type"] == ["json"]
    assert query["pSize"] == ["100"]
    assert query["KEY"] == ["secret"]


@pytest.mark.asyncio
async def test_meal_request_has_fixed_lunch_code_and_dates() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=result("INFO-200"))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://open.neis.go.kr/hub")
    client = NeisClient(None, http_client=http)
    from datetime import date

    assert await client.get_meals("B10", "7010001", date(2026, 8, 1), date(2026, 8, 7)) == []
    await http.aclose()
    query = parse_qs(captured[0].url.query.decode())
    assert query["MMEAL_SC_CODE"] == [LUNCH_CODE]
    assert query["MLSV_FROM_YMD"] == ["20260801"]
    assert query["MLSV_TO_YMD"] == ["20260807"]
    assert query["pSize"] == ["5"]
    assert "KEY" not in query


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, "sample", " SAMPLE "])
async def test_sample_credentials_use_five_row_pages(api_key: str | None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=result("INFO-200"))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://open.neis.go.kr/hub")
    client = NeisClient(api_key, http_client=http)
    assert await client.search_schools("학교") == []
    await http.aclose()

    query = parse_qs(captured[0].url.query.decode())
    assert query["pSize"] == ["5"]
    if api_key is None:
        assert "KEY" not in query
    else:
        assert query["KEY"] == ["sample"]


@pytest.mark.asyncio
async def test_sample_credentials_never_request_later_pages() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=page("schoolInfo", [school_row()], total=6))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://open.neis.go.kr/hub")
    rows = await NeisClient("sample", http_client=http).search_schools("학교")
    await http.aclose()

    assert len(rows) == 1
    assert [parse_qs(request.url.query.decode())["pIndex"] for request in captured] == [["1"]]


@pytest.mark.asyncio
async def test_meals_paginate_and_validate_every_page() -> None:
    requests: list[httpx.Request] = []

    def meal_row(day: int) -> dict[str, object]:
        return {
            "ATPT_OFCDC_SC_CODE": "B10",
            "SD_SCHUL_CODE": "7010001",
            "SCHUL_NM": "테스트고등학교",
            "MLSV_YMD": f"202608{day:02d}",
            "MMEAL_SC_CODE": "2",
            "MMEAL_SC_NM": "중식",
            "DDISH_NM": "밥",
        }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page_index = int(parse_qs(request.url.query.decode())["pIndex"][0])
        rows = [meal_row(day) for day in range(1, 6)] if page_index == 1 else [meal_row(6)]
        return httpx.Response(200, json=page("mealServiceDietInfo", rows, total=101))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://open.neis.go.kr/hub")
    client = NeisClient("real-api-key", http_client=http)
    from datetime import date

    meals = await client.get_meals("B10", "7010001", date(2026, 8, 1), date(2026, 8, 6))
    await http.aclose()

    assert len(meals) == 6
    assert [parse_qs(request.url.query.decode())["pIndex"] for request in requests] == [["1"], ["2"]]
    assert all(parse_qs(request.url.query.decode())["pSize"] == ["100"] for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["ERROR-300", "ERROR-500"])
async def test_embedded_neis_error_is_not_empty_data(code: str) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=result(code)))
    http = httpx.AsyncClient(transport=transport, base_url="https://open.neis.go.kr/hub")
    with pytest.raises(UpstreamError) as error:
        await NeisClient(None, http_client=http).search_schools("학교")
    await http.aclose()
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_malformed_schema_is_rejected() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"schoolInfo": [{"head": []}]}))
    http = httpx.AsyncClient(transport=transport, base_url="https://open.neis.go.kr/hub")
    with pytest.raises(UpstreamError) as error:
        await NeisClient(None, http_client=http).search_schools("학교")
    await http.aclose()
    assert error.value.code == "INVALID_NEIS_RESPONSE"


@pytest.mark.asyncio
async def test_timeout_is_service_unavailable() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    http = httpx.AsyncClient(transport=httpx.MockTransport(timeout), base_url="https://open.neis.go.kr/hub")
    with pytest.raises(UpstreamUnavailableError):
        await NeisClient("do-not-leak", http_client=http).search_schools("학교")
    await http.aclose()
