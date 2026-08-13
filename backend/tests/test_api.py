from urllib.parse import parse_qs

import httpx
import pytest

from conftest import app_client, page, result, school_row


@pytest.mark.asyncio
async def test_health(app_client: app_client) -> None:
    async with app_client(httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_search_contract_trimming_and_key_is_upstream_only(app_client: app_client) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=page("schoolInfo", [school_row()]))

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get("/api/schools", params={"query": "  테스트고  "})

    assert response.status_code == 200
    assert response.json() == {
        "schools": [
            {
                "educationOfficeCode": "B10",
                "schoolCode": "7010001",
                "name": "테스트고등학교",
                "region": "서울특별시",
                "schoolType": "고등학교",
            }
        ]
    }
    assert "test-api-key" not in response.text
    query = parse_qs(captured[0].url.query.decode())
    assert query["SCHUL_NM"] == ["테스트고"]
    assert query["KEY"] == ["test-api-key"]


@pytest.mark.asyncio
async def test_empty_search_is_400_without_upstream_call(app_client: app_client) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get("/api/schools", params={"query": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"
    assert calls == 0


@pytest.mark.asyncio
async def test_missing_query_uses_error_envelope(app_client: app_client) -> None:
    async with app_client(httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        response = await client.get("/api/schools")
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "요청 값이 API 계약에 맞지 않습니다.",
        }
    }


@pytest.mark.asyncio
async def test_meals_are_normalized_sorted_and_optional_fields_are_null(app_client: app_client) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/schoolInfo"):
            return httpx.Response(200, json=page("schoolInfo", [school_row()]))
        rows = [
            {
                "ATPT_OFCDC_SC_CODE": "B10",
                "SD_SCHUL_CODE": "7010001",
                "SCHUL_NM": "테스트고등학교",
                "MLSV_YMD": "20260803",
                "MMEAL_SC_CODE": "2",
                "MMEAL_SC_NM": "중식",
                "DDISH_NM": "밥 (1)<br/>김치 (9)",
                "CAL_INFO": "700 Kcal",
                "MLSV_FGR": 120,
            },
            {
                "ATPT_OFCDC_SC_CODE": "B10",
                "SD_SCHUL_CODE": "7010001",
                "SCHUL_NM": "테스트고등학교",
                "MLSV_YMD": "20260801",
                "MMEAL_SC_CODE": "2",
                "MMEAL_SC_NM": "중식",
                "DDISH_NM": "국<br>과일",
                "NTR_INFO": "단백질 20g",
                "ORPLC_INFO": "쌀: 국내산",
            },
        ]
        return httpx.Response(200, json=page("mealServiceDietInfo", rows))

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get(
            "/api/schools/7010001/meals",
            params={"educationOfficeCode": "B10", "from": "2026-08-01", "to": "2026-08-03"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["school"]["name"] == "테스트고등학교"
    assert [meal["date"] for meal in body["meals"]] == ["2026-08-01", "2026-08-03"]
    assert body["meals"][0]["menu"] == ["국", "과일"]
    assert body["meals"][0]["calories"] is None
    assert body["meals"][1]["headcount"] == 120
    meal_query = parse_qs(requests[1].url.query.decode())
    assert meal_query["MMEAL_SC_CODE"] == ["2"]
    assert meal_query["MLSV_FROM_YMD"] == ["20260801"]


@pytest.mark.asyncio
async def test_no_meals_is_successful_empty_array(app_client: app_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/schoolInfo"):
            return httpx.Response(200, json=page("schoolInfo", [school_row()]))
        return httpx.Response(200, json=result("INFO-200"))

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get(
            "/api/schools/7010001/meals",
            params={"educationOfficeCode": "B10", "from": "2026-08-01", "to": "2026-08-03"},
        )
    assert response.status_code == 200
    assert response.json()["meals"] == []


@pytest.mark.asyncio
async def test_unknown_school_is_404_without_meal_request(app_client: app_client) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=result("INFO-200"))

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get(
            "/api/schools/missing/meals",
            params={"educationOfficeCode": "B10", "from": "2026-08-01", "to": "2026-08-03"},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCHOOL_NOT_FOUND"
    assert calls == 1


@pytest.mark.asyncio
async def test_invalid_range_is_400_before_upstream(app_client: app_client) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with app_client(httpx.MockTransport(handler)) as client:
        response = await client.get(
            "/api/schools/7010001/meals",
            params={"educationOfficeCode": "B10", "from": "2026-08-04", "to": "2026-08-03"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"
    assert calls == 0


@pytest.mark.asyncio
async def test_neis_error_and_timeout_have_safe_error_contract(app_client: app_client) -> None:
    async with app_client(
        httpx.MockTransport(lambda _: httpx.Response(200, json=result("ERROR-300", "secret details")))
    ) as client:
        error_response = await client.get("/api/schools", params={"query": "학교"})
    assert error_response.status_code == 502
    assert error_response.json()["error"]["code"] == "NEIS_ERROR"
    assert "secret" not in error_response.text

    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("contains test-api-key")

    async with app_client(httpx.MockTransport(timeout)) as client:
        timeout_response = await client.get("/api/schools", params={"query": "학교"})
    assert timeout_response.status_code == 503
    assert timeout_response.json()["error"]["code"] == "NEIS_UNAVAILABLE"
    assert "test-api-key" not in timeout_response.text


@pytest.mark.asyncio
async def test_malformed_neis_schema_is_safe_502(app_client: app_client) -> None:
    async with app_client(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"schoolInfo": [{"head": []}]}))
    ) as client:
        response = await client.get("/api/schools", params={"query": "학교"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_NEIS_RESPONSE"


@pytest.mark.asyncio
async def test_cors_only_allows_configured_origin(app_client: app_client) -> None:
    async with app_client(httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        allowed = await client.options(
            "/api/schools",
            headers={
                "Origin": "http://frontend.test",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = await client.options(
            "/api/schools",
            headers={
                "Origin": "http://other.test",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert allowed.headers["access-control-allow-origin"] == "http://frontend.test"
    assert "access-control-allow-origin" not in denied.headers
