import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const school = {
  educationOfficeCode: "B10",
  schoolCode: "7010536",
  name: "한빛고등학교",
  region: "서울특별시",
  schoolType: "고등학교",
};

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

async function selectSchool(user: ReturnType<typeof userEvent.setup>) {
  vi.mocked(fetch).mockResolvedValueOnce(
    await jsonResponse({ schools: [school] }),
  );
  await user.type(screen.getByLabelText("학교 이름"), "한빛");
  await user.click(screen.getByRole("button", { name: "학교 검색" }));
  await user.click(await screen.findByLabelText(/한빛고등학교/));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("validates an empty school query without sending a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "학교 검색" }));

    expect(screen.getByRole("alert")).toHaveTextContent("학교 이름을 한 글자 이상");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows a distinct empty search result", async () => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse({ schools: [] })));
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("학교 이름"), "없는학교");
    await user.click(screen.getByRole("button", { name: "학교 검색" }));

    expect(await screen.findByText(/일치하는 학교가 없어요/)).toBeInTheDocument();
  });

  it("searches, selects a school, and displays meals", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(<App />);
    await selectSchool(user);

    vi.mocked(fetch).mockResolvedValueOnce(
      await jsonResponse({
        school: {
          educationOfficeCode: school.educationOfficeCode,
          schoolCode: school.schoolCode,
          name: school.name,
        },
        from: "2026-08-03",
        to: "2026-08-04",
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
      }),
    );
    await user.clear(screen.getByLabelText("시작일"));
    await user.type(screen.getByLabelText("시작일"), "2026-08-03");
    await user.clear(screen.getByLabelText("종료일"));
    await user.type(screen.getByLabelText("종료일"), "2026-08-04");
    await user.click(screen.getByRole("button", { name: "이 기간 급식 보기" }));

    const meal = await screen.findByRole("article");
    expect(within(meal).getByText("현미밥")).toBeInTheDocument();
    expect(within(meal).getByText("된장국 (5.6)")).toBeInTheDocument();
    expect(within(meal).getByText("315명")).toBeInTheDocument();
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining("/api/schools/7010536/meals?"),
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("blocks a reversed date range before requesting meals", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(<App />);
    await selectSchool(user);
    vi.mocked(fetch).mockClear();

    await user.clear(screen.getByLabelText("시작일"));
    await user.type(screen.getByLabelText("시작일"), "2026-08-10");
    await user.clear(screen.getByLabelText("종료일"));
    await user.type(screen.getByLabelText("종료일"), "2026-08-01");
    await user.click(screen.getByRole("button", { name: "이 기간 급식 보기" }));

    expect(screen.getByRole("alert")).toHaveTextContent("시작일은 종료일보다");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("clears previous meals when another school is selected", async () => {
    const secondSchool = { ...school, schoolCode: "222", name: "새빛고등학교" };
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(<App />);

    vi.mocked(fetch).mockResolvedValueOnce(await jsonResponse({ schools: [school, secondSchool] }));
    await user.type(screen.getByLabelText("학교 이름"), "빛고");
    await user.click(screen.getByRole("button", { name: "학교 검색" }));
    await user.click(await screen.findByLabelText(/한빛고등학교/));
    vi.mocked(fetch).mockResolvedValueOnce(
      await jsonResponse({
        school: { educationOfficeCode: "B10", schoolCode: "7010536", name: school.name },
        from: "2026-08-03",
        to: "2026-08-03",
        meals: [{ date: "2026-08-03", mealType: "중식", menu: ["현미밥"], calories: null, nutrition: null, origin: null, headcount: null }],
      }),
    );
    await user.click(screen.getByRole("button", { name: "이 기간 급식 보기" }));
    await screen.findByText("현미밥");

    await user.click(screen.getByLabelText(/새빛고등학교/));

    await waitFor(() => expect(screen.queryByText("현미밥")).not.toBeInTheDocument());
  });

  it("clears previous meals when the date range changes", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(<App />);
    await selectSchool(user);
    vi.mocked(fetch).mockResolvedValueOnce(
      await jsonResponse({
        school: { educationOfficeCode: "B10", schoolCode: "7010536", name: school.name },
        from: "2026-08-03",
        to: "2026-08-03",
        meals: [{ date: "2026-08-03", mealType: "중식", menu: ["현미밥"], calories: null, nutrition: null, origin: null, headcount: null }],
      }),
    );
    await user.click(screen.getByRole("button", { name: "이 기간 급식 보기" }));
    await screen.findByText("현미밥");

    await user.clear(screen.getByLabelText("종료일"));
    await user.type(screen.getByLabelText("종료일"), "2026-08-10");

    expect(screen.queryByText("현미밥")).not.toBeInTheDocument();
  });

  it("shows backend errors instead of stale results", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(<App />);
    await selectSchool(user);
    vi.mocked(fetch).mockResolvedValueOnce(
      await jsonResponse({ error: { code: "NEIS_UNAVAILABLE", message: "급식 서비스에 잠시 연결할 수 없습니다." } }, 503),
    );

    await user.click(screen.getByRole("button", { name: "이 기간 급식 보기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("급식 서비스에 잠시 연결");
  });
});
