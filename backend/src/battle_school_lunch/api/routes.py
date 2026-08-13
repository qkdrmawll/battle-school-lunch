from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from battle_school_lunch.models import MealSearchResponse, SchoolSearchResponse
from battle_school_lunch.services.schools import SchoolService

router = APIRouter()


def get_service(request: Request) -> SchoolService:
    return request.app.state.school_service


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/schools", response_model=SchoolSearchResponse)
async def search_schools(
    query: Annotated[str, Query()],
    service: Annotated[SchoolService, Depends(get_service)],
) -> SchoolSearchResponse:
    return await service.search(query)


@router.get("/api/schools/{schoolCode}/meals", response_model=MealSearchResponse)
async def get_meals(
    schoolCode: Annotated[str, Path()],
    education_office_code: Annotated[str, Query(alias="educationOfficeCode")],
    from_value: Annotated[str, Query(alias="from")],
    to_value: Annotated[str, Query(alias="to")],
    service: Annotated[SchoolService, Depends(get_service)],
) -> MealSearchResponse:
    return await service.meals(schoolCode, education_office_code, from_value, to_value)
