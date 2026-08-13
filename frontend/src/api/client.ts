import type { Meal, MealsResponse, School } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code = "REQUEST_FAILED",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSchool(value: unknown): value is School {
  return (
    isRecord(value) &&
    typeof value.educationOfficeCode === "string" &&
    typeof value.schoolCode === "string" &&
    typeof value.name === "string" &&
    typeof value.region === "string" &&
    typeof value.schoolType === "string"
  );
}

function isMeal(value: unknown): value is Meal {
  return (
    isRecord(value) &&
    typeof value.date === "string" &&
    typeof value.mealType === "string" &&
    Array.isArray(value.menu) &&
    value.menu.every((item) => typeof item === "string") &&
    (value.calories === null || typeof value.calories === "string") &&
    (value.nutrition === null || typeof value.nutrition === "string") &&
    (value.origin === null || typeof value.origin === "string") &&
    (value.headcount === null || typeof value.headcount === "number")
  );
}

function isMealsResponse(value: unknown): value is MealsResponse {
  return (
    isRecord(value) &&
    isRecord(value.school) &&
    typeof value.school.educationOfficeCode === "string" &&
    typeof value.school.schoolCode === "string" &&
    typeof value.school.name === "string" &&
    typeof value.from === "string" &&
    typeof value.to === "string" &&
    Array.isArray(value.meals) &&
    value.meals.every(isMeal)
  );
}

async function requestJson(url: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("서버가 올바르지 않은 응답을 반환했습니다.");
  }

  if (!response.ok) {
    if (
      isRecord(payload) &&
      isRecord(payload.error) &&
      typeof payload.error.message === "string"
    ) {
      const code =
        typeof payload.error.code === "string" ? payload.error.code : "REQUEST_FAILED";
      throw new ApiError(payload.error.message, code);
    }
    throw new ApiError("요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }

  return payload;
}

export async function searchSchools(
  query: string,
  signal?: AbortSignal,
): Promise<School[]> {
  const payload = await requestJson(
    `/api/schools?${new URLSearchParams({ query })}`,
    signal,
  );
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.schools) ||
    !payload.schools.every(isSchool)
  ) {
    throw new ApiError("학교 검색 응답 형식을 확인할 수 없습니다.");
  }
  return payload.schools;
}

export async function getMeals(
  school: School,
  from: string,
  to: string,
  signal?: AbortSignal,
): Promise<MealsResponse> {
  const query = new URLSearchParams({
    educationOfficeCode: school.educationOfficeCode,
    from,
    to,
  });
  const payload = await requestJson(
    `/api/schools/${encodeURIComponent(school.schoolCode)}/meals?${query}`,
    signal,
  );
  if (!isMealsResponse(payload)) {
    throw new ApiError("급식 조회 응답 형식을 확인할 수 없습니다.");
  }
  return payload;
}
