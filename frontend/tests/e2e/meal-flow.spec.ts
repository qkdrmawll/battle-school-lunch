import { expect, test } from "@playwright/test";

const school = {
  educationOfficeCode: "B10",
  schoolCode: "7010536",
  name: "한빛고등학교",
  region: "서울특별시",
  schoolType: "고등학교",
};

test("completes the school search and lunch lookup flow", async ({ page }) => {
  const requestedUrls: string[] = [];
  await page.route("**/api/schools**", async (route) => {
    const url = new URL(route.request().url());
    requestedUrls.push(url.pathname);
    if (url.pathname === "/api/schools") {
      await route.fulfill({ json: { schools: [school] } });
      return;
    }
    await route.fulfill({
      json: {
        school: {
          educationOfficeCode: school.educationOfficeCode,
          schoolCode: school.schoolCode,
          name: school.name,
        },
        from: "2026-08-03",
        to: "2026-08-03",
        meals: [
          {
            date: "2026-08-03",
            mealType: "중식",
            menu: ["현미밥", "된장국 (5.6)"],
            calories: "720 Kcal",
            nutrition: "탄수화물(g): 98",
            origin: "쌀: 국내산",
            headcount: 315,
          },
        ],
      },
    });
  });

  await page.goto("/");
  await page.getByLabel("학교 이름").fill("한빛");
  await page.getByRole("button", { name: "학교 검색" }).click();
  await page.getByLabel(/한빛고등학교/).check();
  await page.getByLabel("시작일").fill("2026-08-03");
  await page.getByLabel("종료일").fill("2026-08-03");
  await page.getByRole("button", { name: "이 기간 급식 보기" }).click();

  await expect(page.getByRole("heading", { name: "한빛고등학교 중식" })).toBeVisible();
  await expect(page.getByText("현미밥")).toBeVisible();
  expect(requestedUrls).toEqual([
    "/api/schools",
    "/api/schools/7010536/meals",
  ]);
  expect(requestedUrls.every((url) => !url.includes("neis"))).toBe(true);
});

test("distinguishes empty and invalid flows", async ({ page }) => {
  await page.route("**/api/schools?*", (route) =>
    route.fulfill({ json: { schools: [] } }),
  );
  await page.goto("/");
  await page.getByLabel("학교 이름").fill("없는학교");
  await page.getByRole("button", { name: "학교 검색" }).click();
  await expect(page.getByText(/일치하는 학교가 없어요/)).toBeVisible();

  await page.getByLabel("학교 이름").fill("");
  await page.getByRole("button", { name: "학교 검색" }).click();
  await expect(page.getByRole("alert")).toContainText("한 글자 이상");
});
