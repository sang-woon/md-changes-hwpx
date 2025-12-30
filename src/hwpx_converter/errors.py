"""
에러 처리 표준화 모듈

TRD 2.8 예외/오류 처리 표준에 따른 에러 코드 및 메시지 정의
"""

from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    """표준 에러 코드"""

    # 시스템 에러
    E_PANDOC_NOT_FOUND = "E_PANDOC_NOT_FOUND"
    E_INTERNAL_ERROR = "E_INTERNAL_ERROR"

    # 변환 에러
    E_CONVERSION_FAILED = "E_CONVERSION_FAILED"
    E_CONVERSION_TIMEOUT = "E_CONVERSION_TIMEOUT"

    # 템플릿 에러
    E_TEMPLATE_INVALID = "E_TEMPLATE_INVALID"
    E_TEMPLATE_NOT_FOUND = "E_TEMPLATE_NOT_FOUND"

    # 입력 에러
    E_INPUT_TOO_LARGE = "E_INPUT_TOO_LARGE"
    E_UNSUPPORTED_MARKDOWN = "E_UNSUPPORTED_MARKDOWN"
    E_INVALID_INPUT = "E_INVALID_INPUT"
    E_FILE_NOT_FOUND = "E_FILE_NOT_FOUND"

    # 작업 에러
    E_JOB_NOT_FOUND = "E_JOB_NOT_FOUND"
    E_JOB_EXPIRED = "E_JOB_EXPIRED"


# 사용자 친화적 에러 메시지 (업무용)
ERROR_MESSAGES = {
    ErrorCode.E_PANDOC_NOT_FOUND: "문서 변환 엔진(Pandoc)을 찾을 수 없습니다. 시스템 관리자에게 문의하세요.",
    ErrorCode.E_INTERNAL_ERROR: "내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
    ErrorCode.E_CONVERSION_FAILED: "문서 변환에 실패했습니다. 마크다운 형식을 확인해주세요.",
    ErrorCode.E_CONVERSION_TIMEOUT: "변환 시간이 초과되었습니다. 문서 크기를 줄여서 다시 시도해주세요.",
    ErrorCode.E_TEMPLATE_INVALID: "템플릿 서식이 유효하지 않습니다. 스타일/글머리표 설정을 확인해주세요.",
    ErrorCode.E_TEMPLATE_NOT_FOUND: "지정된 템플릿을 찾을 수 없습니다.",
    ErrorCode.E_INPUT_TOO_LARGE: "입력 파일이 너무 큽니다. 파일 크기를 줄여주세요.",
    ErrorCode.E_UNSUPPORTED_MARKDOWN: "입력 문서 구조가 표준 규칙과 다릅니다. 목록 들여쓰기를 확인해주세요.",
    ErrorCode.E_INVALID_INPUT: "입력 형식이 올바르지 않습니다.",
    ErrorCode.E_FILE_NOT_FOUND: "파일을 찾을 수 없습니다.",
    ErrorCode.E_JOB_NOT_FOUND: "변환 작업을 찾을 수 없습니다.",
    ErrorCode.E_JOB_EXPIRED: "변환 파일이 만료되었습니다. 다시 변환해주세요.",
}


class HwpxConverterError(Exception):
    """HWPX 변환기 기본 예외 클래스"""

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        detail: Optional[str] = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "알 수 없는 오류가 발생했습니다.")
        self.detail = detail  # 내부 디버깅용 상세 정보
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """API 응답용 딕셔너리 변환"""
        result = {
            "error_code": self.code.value,
            "error_message": self.message,
        }
        # detail은 운영 환경에서 노출하지 않음 (로그에만 기록)
        return result


class PandocNotFoundError(HwpxConverterError):
    """Pandoc 실행 파일을 찾을 수 없을 때"""

    def __init__(self, detail: Optional[str] = None):
        super().__init__(ErrorCode.E_PANDOC_NOT_FOUND, detail=detail)


class ConversionFailedError(HwpxConverterError):
    """변환 실패 시"""

    def __init__(self, message: Optional[str] = None, detail: Optional[str] = None):
        super().__init__(ErrorCode.E_CONVERSION_FAILED, message=message, detail=detail)


class TemplateInvalidError(HwpxConverterError):
    """템플릿이 유효하지 않을 때"""

    def __init__(self, message: Optional[str] = None, detail: Optional[str] = None):
        super().__init__(ErrorCode.E_TEMPLATE_INVALID, message=message, detail=detail)


class TemplateNotFoundError(HwpxConverterError):
    """템플릿을 찾을 수 없을 때"""

    def __init__(self, template_id: Optional[str] = None):
        detail = f"Template ID: {template_id}" if template_id else None
        super().__init__(ErrorCode.E_TEMPLATE_NOT_FOUND, detail=detail)


class InputTooLargeError(HwpxConverterError):
    """입력 파일이 너무 클 때"""

    def __init__(self, size: int, max_size: int):
        detail = f"Input size: {size} bytes, Max allowed: {max_size} bytes"
        super().__init__(ErrorCode.E_INPUT_TOO_LARGE, detail=detail)


class UnsupportedMarkdownError(HwpxConverterError):
    """지원하지 않는 마크다운 형식일 때"""

    def __init__(self, message: Optional[str] = None, detail: Optional[str] = None):
        super().__init__(ErrorCode.E_UNSUPPORTED_MARKDOWN, message=message, detail=detail)


class JobNotFoundError(HwpxConverterError):
    """변환 작업을 찾을 수 없을 때"""

    def __init__(self, job_id: str):
        detail = f"Job ID: {job_id}"
        super().__init__(ErrorCode.E_JOB_NOT_FOUND, detail=detail)


class JobExpiredError(HwpxConverterError):
    """변환 파일이 만료되었을 때"""

    def __init__(self, job_id: str):
        detail = f"Job ID: {job_id}"
        super().__init__(ErrorCode.E_JOB_EXPIRED, detail=detail)
