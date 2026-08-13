import re
from datetime import date, datetime

from battle_school_lunch.clients.neis import MealRow, NeisClient
from battle_school_lunch.errors import AppError
from battle_school_lunch.models import Meal, MealSearchResponse, School, SchoolSearchResponse, SchoolSummary

BREAK_PATTERN = re.compile(r"<br\s*/?>", flags=re.IGNORECASE)


def normalize_query(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        raise AppError(400, "INVALID_QUERY", "학교명 일부를 입력해 주세요.")
    return normalized


def require_code(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AppError(400, "INVALID_SCHOOL_IDENTIFIER", f"{field_name}은(는) 비어 있을 수 없습니다.")
    return normalized


def parse_date_range(from_value: str, to_value: str) -> tuple[date, date]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", from_value) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", to_value):
        raise AppError(400, "INVALID_DATE", "날짜는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.")
    try:
        from_date = date.fromisoformat(from_value)
        to_date = date.fromisoformat(to_value)
    except ValueError:
        raise AppError(400, "INVALID_DATE", "날짜는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.") from None
    if from_date > to_date:
        raise AppError(400, "INVALID_DATE_RANGE", "시작일은 종료일보다 늦을 수 없습니다.")
    return from_date, to_date


def normalize_menu(value: str) -> list[str]:
    return [item.strip() for item in BREAK_PATTERN.split(value) if item.strip()]


def meal_from_row(row: MealRow) -> Meal:
    return Meal(
        date=datetime.strptime(row.meal_date, "%Y%m%d").date(),
        mealType=row.meal_type,
        menu=normalize_menu(row.dish_name),
        calories=row.calories,
        nutrition=row.nutrition,
        origin=row.origin,
        headcount=row.headcount,
    )


class SchoolService:
    def __init__(self, client: NeisClient) -> None:
        self._client = client

    async def search(self, raw_query: str) -> SchoolSearchResponse:
        rows = await self._client.search_schools(normalize_query(raw_query))
        return SchoolSearchResponse(
            schools=[
                School(
                    educationOfficeCode=row.education_office_code,
                    schoolCode=row.school_code,
                    name=row.name,
                    region=row.region,
                    schoolType=row.school_type,
                )
                for row in rows
            ]
        )

    async def meals(
        self,
        raw_school_code: str,
        raw_education_office_code: str,
        from_value: str,
        to_value: str,
    ) -> MealSearchResponse:
        school_code = require_code(raw_school_code, "학교 코드")
        office_code = require_code(raw_education_office_code, "교육청 코드")
        from_date, to_date = parse_date_range(from_value, to_value)
        school = await self._client.get_school(office_code, school_code)
        if school is None:
            raise AppError(404, "SCHOOL_NOT_FOUND", "요청한 학교를 찾을 수 없습니다.")
        rows = await self._client.get_meals(office_code, school_code, from_date, to_date)
        meals = sorted((meal_from_row(row) for row in rows), key=lambda meal: meal.date)
        return MealSearchResponse(
            school=SchoolSummary(
                educationOfficeCode=school.education_office_code,
                schoolCode=school.school_code,
                name=school.name,
            ),
            **{"from": from_date, "to": to_date},
            meals=meals,
        )
