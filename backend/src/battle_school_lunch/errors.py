from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    code: str
    message: str


class UpstreamError(AppError):
    def __init__(self, code: str = "NEIS_ERROR", message: str = "교육행정정보 서비스 조회에 실패했습니다.") -> None:
        super().__init__(502, code, message)


class UpstreamUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(503, "NEIS_UNAVAILABLE", "교육행정정보 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.")
