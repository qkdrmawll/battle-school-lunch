export interface School {
  educationOfficeCode: string;
  schoolCode: string;
  name: string;
  region: string;
  schoolType: string;
}

export interface Meal {
  date: string;
  mealType: string;
  menu: string[];
  calories: string | null;
  nutrition: string | null;
  origin: string | null;
  headcount: number | null;
}

export interface MealsResponse {
  school: Pick<School, "educationOfficeCode" | "schoolCode" | "name">;
  from: string;
  to: string;
  meals: Meal[];
}

export type RequestStatus = "idle" | "loading" | "success" | "empty" | "error";
