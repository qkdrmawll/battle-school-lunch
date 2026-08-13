from __future__ import annotations

import math
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from battle_school_lunch.errors import UpstreamError, UpstreamUnavailableError

BASE_URL = "https://open.neis.go.kr/hub"
LUNCH_CODE = "2"
PAGE_SIZE = 100
SAMPLE_PAGE_SIZE = 5
SUCCESS_CODE = "INFO-000"
NO_DATA_CODE = "INFO-200"


class NeisModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class NeisResult(NeisModel):
    code: str = Field(alias="CODE")
    message: str = Field(alias="MESSAGE")


class SchoolRow(NeisModel):
    education_office_code: str = Field(alias="ATPT_OFCDC_SC_CODE")
    school_code: str = Field(alias="SD_SCHUL_CODE")
    name: str = Field(alias="SCHUL_NM")
    region: str = Field(alias="LCTN_SC_NM")
    school_type: str = Field(alias="SCHUL_KND_SC_NM")


class MealRow(NeisModel):
    education_office_code: str = Field(alias="ATPT_OFCDC_SC_CODE")
    school_code: str = Field(alias="SD_SCHUL_CODE")
    school_name: str = Field(alias="SCHUL_NM")
    meal_date: str = Field(alias="MLSV_YMD", pattern=r"^\d{8}$")
    meal_code: str = Field(alias="MMEAL_SC_CODE")
    meal_type: str = Field(alias="MMEAL_SC_NM")
    dish_name: str = Field(alias="DDISH_NM")
    calories: str | None = Field(default=None, alias="CAL_INFO")
    nutrition: str | None = Field(default=None, alias="NTR_INFO")
    origin: str | None = Field(default=None, alias="ORPLC_INFO")
    headcount: int | None = Field(default=None, alias="MLSV_FGR")


class NeisClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        normalized_key = api_key.strip() if api_key and api_key.strip() else None
        self._api_key = "sample" if normalized_key and normalized_key.casefold() == "sample" else normalized_key
        self._sample_mode = self._api_key is None or self._api_key == "sample"
        self._page_size = SAMPLE_PAGE_SIZE if self._sample_mode else PAGE_SIZE
        self._timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _params(self, **values: str | int) -> dict[str, str | int]:
        params: dict[str, str | int] = {"Type": "json", **values}
        if self._api_key:
            params["KEY"] = self._api_key
        return params

    async def _get(self, endpoint: str, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            response = await self._client.get(endpoint, params=params, timeout=self._timeout_seconds)
            response.raise_for_status()
        except httpx.RequestError:
            raise UpstreamUnavailableError() from None
        except httpx.HTTPStatusError:
            raise UpstreamError() from None

        try:
            payload = response.json()
        except ValueError:
            raise UpstreamError("INVALID_NEIS_RESPONSE", "교육행정정보 서비스 응답 형식이 올바르지 않습니다.") from None
        if not isinstance(payload, dict):
            raise UpstreamError("INVALID_NEIS_RESPONSE", "교육행정정보 서비스 응답 형식이 올바르지 않습니다.")
        return payload

    @staticmethod
    def _top_level_result(payload: dict[str, Any]) -> str | None:
        if "RESULT" not in payload:
            return None
        try:
            result = NeisResult.model_validate(payload["RESULT"])
        except ValidationError:
            raise UpstreamError("INVALID_NEIS_RESPONSE", "교육행정정보 서비스 응답 형식이 올바르지 않습니다.") from None
        if result.code not in {SUCCESS_CODE, NO_DATA_CODE}:
            raise UpstreamError()
        return result.code

    @staticmethod
    def _extract_page(payload: dict[str, Any], key: str, row_model: type[NeisModel]) -> tuple[int, list[NeisModel]]:
        top_result = NeisClient._top_level_result(payload)
        if top_result == NO_DATA_CODE:
            return 0, []
        try:
            blocks = payload[key]
            if not isinstance(blocks, list) or len(blocks) < 2:
                raise TypeError
            head = blocks[0]["head"]
            rows = blocks[1]["row"]
            if not isinstance(head, list) or not isinstance(rows, list):
                raise TypeError
            total = next(item["list_total_count"] for item in head if "list_total_count" in item)
            result_data = next(item["RESULT"] for item in head if "RESULT" in item)
            result = NeisResult.model_validate(result_data)
            if result.code == NO_DATA_CODE:
                return 0, []
            if result.code != SUCCESS_CODE or not isinstance(total, int) or total < 0:
                raise UpstreamError()
            return total, [row_model.model_validate(row) for row in rows]
        except UpstreamError:
            raise
        except (KeyError, TypeError, StopIteration, ValidationError):
            raise UpstreamError("INVALID_NEIS_RESPONSE", "교육행정정보 서비스 응답 형식이 올바르지 않습니다.") from None

    async def search_schools(self, query: str) -> list[SchoolRow]:
        page = 1
        results: list[SchoolRow] = []
        while True:
            payload = await self._get(
                "/schoolInfo",
                self._params(pIndex=page, pSize=self._page_size, SCHUL_NM=query),
            )
            total, rows = self._extract_page(payload, "schoolInfo", SchoolRow)
            results.extend(row for row in rows if isinstance(row, SchoolRow))
            if self._sample_mode or page >= math.ceil(total / self._page_size):
                return results
            page += 1

    async def get_school(self, education_office_code: str, school_code: str) -> SchoolRow | None:
        payload = await self._get(
            "/schoolInfo",
            self._params(
                pIndex=1,
                pSize=self._page_size,
                ATPT_OFCDC_SC_CODE=education_office_code,
                SD_SCHUL_CODE=school_code,
            ),
        )
        _, rows = self._extract_page(payload, "schoolInfo", SchoolRow)
        for row in rows:
            if (
                isinstance(row, SchoolRow)
                and row.education_office_code == education_office_code
                and row.school_code == school_code
            ):
                return row
        return None

    async def get_meals(
        self,
        education_office_code: str,
        school_code: str,
        from_date: date,
        to_date: date,
    ) -> list[MealRow]:
        page = 1
        meals: list[MealRow] = []
        while True:
            payload = await self._get(
                "/mealServiceDietInfo",
                self._params(
                    pIndex=page,
                    pSize=self._page_size,
                    ATPT_OFCDC_SC_CODE=education_office_code,
                    SD_SCHUL_CODE=school_code,
                    MLSV_FROM_YMD=from_date.strftime("%Y%m%d"),
                    MLSV_TO_YMD=to_date.strftime("%Y%m%d"),
                    MMEAL_SC_CODE=LUNCH_CODE,
                ),
            )
            total, rows = self._extract_page(payload, "mealServiceDietInfo", MealRow)
            meals.extend(row for row in rows if isinstance(row, MealRow))
            if self._sample_mode or page >= math.ceil(total / self._page_size):
                break
            page += 1
        if any(
            row.education_office_code != education_office_code
            or row.school_code != school_code
            or row.meal_code != LUNCH_CODE
            or not from_date.strftime("%Y%m%d") <= row.meal_date <= to_date.strftime("%Y%m%d")
            for row in meals
        ):
            raise UpstreamError("INVALID_NEIS_RESPONSE", "교육행정정보 서비스 응답 형식이 올바르지 않습니다.")
        return meals
