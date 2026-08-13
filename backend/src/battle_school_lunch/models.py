from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class School(ApiModel):
    education_office_code: str = Field(alias="educationOfficeCode")
    school_code: str = Field(alias="schoolCode")
    name: str
    region: str
    school_type: str = Field(alias="schoolType")


class SchoolSummary(ApiModel):
    education_office_code: str = Field(alias="educationOfficeCode")
    school_code: str = Field(alias="schoolCode")
    name: str


class SchoolSearchResponse(ApiModel):
    schools: list[School]


class Meal(ApiModel):
    date: date
    meal_type: str = Field(alias="mealType")
    menu: list[str]
    calories: str | None
    nutrition: str | None
    origin: str | None
    headcount: int | None


class MealSearchResponse(ApiModel):
    school: SchoolSummary
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    meals: list[Meal]


class ErrorDetail(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorDetail
