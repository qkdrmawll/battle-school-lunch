import { FormEvent, useRef, useState } from "react";
import { ApiError, getMeals, searchSchools } from "./api/client";
import type { MealsResponse, RequestStatus, School } from "./types";
import "./styles.css";

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

function initialDates(): { from: string; to: string } {
  const today = new Date();
  const end = new Date(today);
  end.setDate(today.getDate() + 7);
  return {
    from: today.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  };
}

function StatusMessage({
  children,
  tone = "info",
}: {
  children: React.ReactNode;
  tone?: "info" | "error" | "empty";
}) {
  return (
    <div className={`status status--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <span aria-hidden="true">{tone === "error" ? "!" : tone === "empty" ? "?" : "…"}</span>
      <p>{children}</p>
    </div>
  );
}

export default function App() {
  const defaults = initialDates();
  const [query, setQuery] = useState("");
  const [schools, setSchools] = useState<School[]>([]);
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null);
  const [searchStatus, setSearchStatus] = useState<RequestStatus>("idle");
  const [searchMessage, setSearchMessage] = useState("");
  const [from, setFrom] = useState(defaults.from);
  const [to, setTo] = useState(defaults.to);
  const [mealStatus, setMealStatus] = useState<RequestStatus>("idle");
  const [mealMessage, setMealMessage] = useState("");
  const [mealResult, setMealResult] = useState<MealsResponse | null>(null);
  const searchController = useRef<AbortController | null>(null);
  const mealController = useRef<AbortController | null>(null);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      setSearchStatus("error");
      setSearchMessage("학교 이름을 한 글자 이상 입력해 주세요.");
      return;
    }

    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setSearchStatus("loading");
    setSearchMessage("");
    setSchools([]);
    setSelectedSchool(null);
    setMealStatus("idle");
    setMealResult(null);
    mealController.current?.abort();

    try {
      const results = await searchSchools(normalizedQuery, controller.signal);
      setSchools(results);
      setSearchStatus(results.length === 0 ? "empty" : "success");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setSearchStatus("error");
      setSearchMessage(
        error instanceof ApiError
          ? error.message
          : "학교 검색 중 문제가 발생했습니다. 다시 시도해 주세요.",
      );
    }
  }

  function selectSchool(school: School) {
    mealController.current?.abort();
    setSelectedSchool(school);
    setMealStatus("idle");
    setMealResult(null);
    setMealMessage("");
  }

  function updateDate(value: string, field: "from" | "to") {
    mealController.current?.abort();
    setMealStatus("idle");
    setMealResult(null);
    setMealMessage("");
    if (field === "from") {
      setFrom(value);
    } else {
      setTo(value);
    }
  }

  async function handleMeals(event: FormEvent) {
    event.preventDefault();
    if (!selectedSchool) {
      setMealStatus("error");
      setMealMessage("먼저 검색 결과에서 학교를 선택해 주세요.");
      return;
    }
    if (!from || !to) {
      setMealStatus("error");
      setMealMessage("조회 시작일과 종료일을 모두 입력해 주세요.");
      return;
    }
    if (from > to) {
      setMealStatus("error");
      setMealMessage("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }

    mealController.current?.abort();
    const controller = new AbortController();
    mealController.current = controller;
    setMealStatus("loading");
    setMealMessage("");
    setMealResult(null);

    try {
      const result = await getMeals(selectedSchool, from, to, controller.signal);
      setMealResult(result);
      setMealStatus(result.meals.length === 0 ? "empty" : "success");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMealStatus("error");
      setMealMessage(
        error instanceof ApiError
          ? error.message
          : "급식 조회 중 문제가 발생했습니다. 다시 시도해 주세요.",
      );
    }
  }

  return (
    <main>
      <header className="hero">
        <nav className="brand" aria-label="서비스">
          <span className="brand__mark" aria-hidden="true">ㅂ</span>
          <strong>급식 배틀</strong>
        </nav>
        <div className="hero__content">
          <p className="eyebrow">오늘의 점심이 궁금하다면</p>
          <h1>학교 급식,<br /><em>한눈에 맛있게.</em></h1>
          <p className="hero__description">
            학교 이름을 검색하고 원하는 기간을 선택하면<br className="desktop-only" />
            날짜별 중식 메뉴를 바로 확인할 수 있어요.
          </p>
        </div>
        <div className="hero__art" aria-hidden="true">
          <div className="tray">
            <span>🍚</span><span>🥗</span><span>🍲</span>
          </div>
        </div>
      </header>

      <section className="workspace" aria-label="급식 조회">
        <ol className="steps" aria-label="조회 단계">
          <li className={selectedSchool ? "steps__done" : "steps__active"}><span>1</span> 학교 찾기</li>
          <li className={selectedSchool ? "steps__active" : ""}><span>2</span> 날짜 고르기</li>
          <li className={mealStatus === "success" ? "steps__active" : ""}><span>3</span> 급식 보기</li>
        </ol>

        <div className="panel">
          <section className="search-section" aria-labelledby="school-heading">
            <div className="section-heading">
              <span className="number">01</span>
              <div>
                <h2 id="school-heading">학교를 찾아보세요</h2>
                <p>정확한 이름을 몰라도 괜찮아요.</p>
              </div>
            </div>
            <form className="search-form" onSubmit={handleSearch} noValidate>
              <label htmlFor="school-query">학교 이름</label>
              <div className="search-control">
                <input
                  id="school-query"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="예: 서울고, 한빛초"
                  autoComplete="off"
                />
                <button type="submit" disabled={searchStatus === "loading"}>
                  {searchStatus === "loading" ? "찾는 중…" : "학교 검색"}
                </button>
              </div>
            </form>

            {searchStatus === "loading" && <StatusMessage>학교를 찾고 있습니다.</StatusMessage>}
            {searchStatus === "empty" && (
              <StatusMessage tone="empty">일치하는 학교가 없어요. 지역명 없이 학교 이름 일부로 다시 검색해 보세요.</StatusMessage>
            )}
            {searchStatus === "error" && <StatusMessage tone="error">{searchMessage}</StatusMessage>}
            {schools.length > 0 && (
              <fieldset className="school-results">
                <legend>검색 결과 {schools.length}개</legend>
                {schools.map((school) => (
                  <label
                    className={`school-option ${selectedSchool?.schoolCode === school.schoolCode ? "school-option--selected" : ""}`}
                    key={`${school.educationOfficeCode}-${school.schoolCode}`}
                  >
                    <input
                      type="radio"
                      name="school"
                      checked={selectedSchool?.schoolCode === school.schoolCode}
                      onChange={() => selectSchool(school)}
                    />
                    <span className="school-option__check" aria-hidden="true" />
                    <span>
                      <strong>{school.name}</strong>
                      <small>{school.region} · {school.schoolType}</small>
                    </span>
                  </label>
                ))}
              </fieldset>
            )}
          </section>

          <section className={`date-section ${selectedSchool ? "" : "section-disabled"}`} aria-labelledby="date-heading">
            <div className="section-heading">
              <span className="number">02</span>
              <div>
                <h2 id="date-heading">기간을 선택하세요</h2>
                <p>{selectedSchool ? `${selectedSchool.name}의 중식 메뉴를 조회합니다.` : "학교를 선택하면 날짜를 고를 수 있어요."}</p>
              </div>
            </div>
            <form onSubmit={handleMeals} noValidate>
              <div className="date-grid">
                <label>
                  시작일
                  <input type="date" value={from} onChange={(event) => updateDate(event.target.value, "from")} disabled={!selectedSchool} />
                </label>
                <span aria-hidden="true">→</span>
                <label>
                  종료일
                  <input type="date" value={to} onChange={(event) => updateDate(event.target.value, "to")} disabled={!selectedSchool} />
                </label>
              </div>
              <button className="primary-button" type="submit" disabled={!selectedSchool || mealStatus === "loading"}>
                {mealStatus === "loading" ? "급식을 불러오는 중…" : "이 기간 급식 보기"}
              </button>
            </form>
            {mealStatus === "loading" && <StatusMessage>날짜별 중식 메뉴를 불러오고 있습니다.</StatusMessage>}
            {mealStatus === "empty" && (
              <StatusMessage tone="empty">선택한 학교와 기간에 등록된 중식 정보가 없습니다.</StatusMessage>
            )}
            {mealStatus === "error" && <StatusMessage tone="error">{mealMessage}</StatusMessage>}
          </section>
        </div>
      </section>

      {mealStatus === "success" && mealResult && (
        <section className="meal-section" aria-labelledby="meal-heading">
          <div className="meal-section__heading">
            <div>
              <p className="eyebrow">맛있는 일주일</p>
              <h2 id="meal-heading">{mealResult.school.name} 중식</h2>
              <p>{mealResult.from} — {mealResult.to}</p>
            </div>
            <strong>{mealResult.meals.length}<small>끼</small></strong>
          </div>
          <div className="meal-grid">
            {mealResult.meals.map((meal) => (
              <article className="meal-card" key={meal.date}>
                <header>
                  <time dateTime={meal.date}>{formatDate(meal.date)}</time>
                  <span>{meal.mealType}</span>
                </header>
                <ul className="menu-list">
                  {meal.menu.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
                </ul>
                <dl>
                  {meal.calories && <><dt>열량</dt><dd>{meal.calories}</dd></>}
                  {meal.headcount !== null && <><dt>급식 인원</dt><dd>{meal.headcount.toLocaleString("ko-KR")}명</dd></>}
                  {meal.nutrition && <><dt>영양 정보</dt><dd className="pre-line">{meal.nutrition}</dd></>}
                  {meal.origin && <><dt>원산지</dt><dd className="pre-line">{meal.origin}</dd></>}
                </dl>
              </article>
            ))}
          </div>
        </section>
      )}

      <footer>
        <strong>급식 배틀</strong>
        <span>NEIS 교육정보 개방 포털의 데이터를 사용합니다.</span>
      </footer>
    </main>
  );
}
