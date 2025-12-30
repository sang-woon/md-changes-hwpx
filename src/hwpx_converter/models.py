"""
데이터 모델 정의

TRD 2.6 데이터 모델에 따른 Template 및 ConversionJob 모델
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class ConversionStatus(str, Enum):
    """변환 작업 상태"""

    QUEUED = "queued"  # 대기 중
    PROCESSING = "processing"  # 처리 중
    SUCCEEDED = "succeeded"  # 성공
    FAILED = "failed"  # 실패


class Template(BaseModel):
    """
    템플릿 모델

    TRD 2.6 데이터 모델:
    - template_id (PK)
    - version
    - file_path
    - is_default
    - created_at
    """

    template_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    version: str = Field(default="1.0.0", description="템플릿 버전")
    name: str = Field(default="default", description="템플릿 이름")
    file_path: str = Field(..., description="템플릿 파일 경로")
    is_default: bool = Field(default=False, description="기본 템플릿 여부")
    description: Optional[str] = Field(default=None, description="템플릿 설명")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversionJob(BaseModel):
    """
    변환 작업 모델

    TRD 2.6 데이터 모델:
    - conversion_id (PK)
    - user_id (식별자)
    - template_id
    - input_filename
    - input_path
    - output_path
    - status
    - error_code, error_message
    - created_at, finished_at
    """

    conversion_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    user_id: Optional[str] = Field(default=None, description="사용자 식별자")
    template_id: str = Field(default="default", description="사용된 템플릿 ID")
    input_filename: str = Field(..., description="입력 파일명")
    input_path: Optional[str] = Field(default=None, description="입력 파일 경로")
    output_path: Optional[str] = Field(default=None, description="출력 파일 경로")
    status: ConversionStatus = Field(default=ConversionStatus.QUEUED)
    error_code: Optional[str] = Field(default=None, description="에러 코드")
    error_message: Optional[str] = Field(default=None, description="에러 메시지")
    created_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = Field(default=None)

    # 추가 메타데이터 (본문 내용 저장 금지 - TRD 2.9)
    input_size_bytes: Optional[int] = Field(default=None, description="입력 파일 크기")
    output_size_bytes: Optional[int] = Field(default=None, description="출력 파일 크기")
    processing_time_ms: Optional[int] = Field(default=None, description="처리 시간(밀리초)")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def mark_processing(self):
        """처리 중으로 상태 변경"""
        self.status = ConversionStatus.PROCESSING

    def mark_succeeded(self, output_path: str, output_size: int, processing_time_ms: int):
        """성공으로 상태 변경"""
        self.status = ConversionStatus.SUCCEEDED
        self.output_path = output_path
        self.output_size_bytes = output_size
        self.processing_time_ms = processing_time_ms
        self.finished_at = datetime.now()

    def mark_failed(self, error_code: str, error_message: str):
        """실패로 상태 변경"""
        self.status = ConversionStatus.FAILED
        self.error_code = error_code
        self.error_message = error_message
        self.finished_at = datetime.now()

    def is_completed(self) -> bool:
        """완료 여부 확인"""
        return self.status in (ConversionStatus.SUCCEEDED, ConversionStatus.FAILED)

    def output_ready(self) -> bool:
        """출력 파일 준비 여부"""
        return self.status == ConversionStatus.SUCCEEDED and self.output_path is not None


# ============================================================================
# API 요청/응답 모델
# ============================================================================


class ConversionRequest(BaseModel):
    """변환 요청 모델 (API-01)"""

    markdown: Optional[str] = Field(default=None, description="변환할 마크다운 텍스트")
    template_id: str = Field(default="default", description="사용할 템플릿 ID")
    filename: str = Field(default="output", description="출력 파일명 (확장자 제외)")
    preprocess: bool = Field(default=True, description="마크다운 전처리 여부")
    options: Optional[Dict[str, Any]] = Field(default=None, description="추가 옵션")


class ConversionResponse(BaseModel):
    """변환 응답 모델"""

    conversion_id: str
    status: ConversionStatus
    created_at: datetime
    message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversionStatusResponse(BaseModel):
    """변환 상태 조회 응답 (API-02)"""

    conversion_id: str
    status: ConversionStatus
    output_ready: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TemplateResponse(BaseModel):
    """템플릿 정보 응답 (API-04)"""

    template_id: str
    name: str
    version: str
    is_default: bool
    description: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TemplateListResponse(BaseModel):
    """템플릿 목록 응답"""

    templates: list[TemplateResponse]
    total_count: int


class StyleInfo(BaseModel):
    """스타일 정보"""

    level: int
    bullet: str
    font_size_pt: float
    description: str


class MarkdownGuide(BaseModel):
    """마크다운 작성 가이드"""

    input_format: str
    output_format: str
    description: str
