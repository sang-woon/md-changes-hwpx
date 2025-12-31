"""
FastAPI 기반 REST API 서비스

TRD 2.5 API 설계에 따른 엔드포인트 구현:
- POST /v1/conversions - 변환 요청
- GET /v1/conversions/{conversion_id} - 상태 조회
- GET /v1/conversions/{conversion_id}/download - 결과 다운로드
- GET /v1/templates - 템플릿 목록
- POST /v1/templates - 템플릿 업로드
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .converter import HwpxConverter
from .storage import get_storage, init_storage, JobStorage
from .models import (
    ConversionJob,
    ConversionStatus,
    ConversionRequest,
    ConversionResponse,
    ConversionStatusResponse,
    Template,
    TemplateResponse,
    TemplateListResponse,
    StyleInfo,
)
from .errors import (
    HwpxConverterError,
    JobNotFoundError,
    JobExpiredError,
    TemplateNotFoundError,
    ErrorCode,
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 앱 라이프사이클
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리"""
    # 시작 시
    storage = get_storage()
    storage.start_cleanup_thread()
    logger.info("HWPX Converter API started")

    yield

    # 종료 시
    storage.stop_cleanup_thread()
    logger.info("HWPX Converter API stopped")


# ============================================================================
# FastAPI 앱 초기화
# ============================================================================

app = FastAPI(
    title="공공기관 HWPX 변환 서비스",
    description="""
마크다운 문서를 공공기관 보고서 스타일의 HWPX(한글 문서) 파일로 변환하는 API 서비스입니다.

## 주요 기능

* **변환 요청**: 마크다운 텍스트/파일을 HWPX로 변환
* **상태 조회**: 변환 작업 진행 상태 확인
* **결과 다운로드**: 변환된 HWPX 파일 다운로드
* **템플릿 관리**: 커스텀 템플릿 등록 및 관리

## 서식 매핑

| 마크다운 | HWPX 출력 |
|---------|----------|
| `#` | Ⅰ. (대제목) |
| `##` | ① (중제목) |
| `-` | □ (1단계, 13pt) |
| `    -` | ㅇ (2단계, 12pt) |
| `>` | * (주석, 10pt) |
    """,
    version="1.0.0",
    contact={
        "name": "경기도의회 AI입법혁신팀",
        "email": "ai-innovation@ggc.go.kr",
    },
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (웹 UI)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# ChatGPT 프롬프트 템플릿 (PRD FR-01, FR-02)
# ============================================================================

CHATGPT_PROMPT_TEMPLATE = """당신은 공공기관 보고서 초안 작성 전문가입니다.

[필수 출력 규칙]
1. 응답은 반드시 Markdown 문법으로만 작성합니다.
2. 응답 전체를 ```markdown 코드블록 안에 넣어 출력합니다.
3. 설명 문장, 인사말, 부연 설명은 절대 포함하지 않습니다.
4. 서식에 대한 설명(예: "아래는 보고서입니다")을 작성하지 않습니다.

[Markdown 구조 규칙]
- 대제목: # (1개)
- 중제목: ## (2개)
- 1단계 항목: - (대시)
- 2단계 항목: 4칸 들여쓰기 후 - (대시)
- 주석/참고: > (인용)
- 강조: **굵게**

[작성 요청]
주제: {topic}

위 주제에 대해 공공기관 보고서 형식의 Markdown을 작성해 주세요.
- 개조식(글머리 기호) 형태로 작성
- 간결하고 명확한 문장
- 구체적인 수치나 일정 포함"""


# ============================================================================
# 예외 핸들러
# ============================================================================


@app.exception_handler(HwpxConverterError)
async def hwpx_error_handler(request: Request, exc: HwpxConverterError):
    """HWPX 변환 에러 핸들러"""
    status_code = 400
    if exc.code in (ErrorCode.E_JOB_NOT_FOUND, ErrorCode.E_TEMPLATE_NOT_FOUND):
        status_code = 404
    elif exc.code == ErrorCode.E_JOB_EXPIRED:
        status_code = 410
    elif exc.code in (ErrorCode.E_PANDOC_NOT_FOUND, ErrorCode.E_INTERNAL_ERROR):
        status_code = 500

    return JSONResponse(status_code=status_code, content=exc.to_dict())


# ============================================================================
# 상태 확인
# ============================================================================


@app.get("/", response_class=HTMLResponse, tags=["상태"])
async def root():
    """웹 UI 제공"""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="""
        <html>
        <head><title>HWPX 변환 서비스</title></head>
        <body>
            <h1>공공기관 HWPX 변환 서비스</h1>
            <p>API 문서: <a href="/docs">/docs</a></p>
        </body>
        </html>
        """
    )


@app.get("/api", tags=["상태"])
async def api_status():
    """API 상태 확인"""
    return {
        "service": "공공기관 HWPX 변환 서비스",
        "version": "1.0.0",
        "status": "running",
        "api_version": "v1",
    }


@app.get("/healthz", tags=["상태"])
async def health_check():
    """헬스체크 (TRD 2.10)"""
    try:
        # Pandoc 실행 가능 여부 확인
        import pypandoc

        pandoc_version = pypandoc.get_pandoc_version()
        return {
            "status": "healthy",
            "pandoc_version": pandoc_version,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


# ============================================================================
# 변환 API (TRD 2.5)
# ============================================================================


@app.post(
    "/v1/conversions",
    response_model=ConversionResponse,
    tags=["변환"],
    summary="변환 요청 (API-01)",
)
async def create_conversion(
    file: Optional[UploadFile] = File(default=None, description="마크다운 파일"),
    markdown: Optional[str] = Form(default=None, description="마크다운 텍스트"),
    template_id: str = Form(default="default", description="템플릿 ID"),
    filename: str = Form(default="output", description="출력 파일명"),
    preprocess: bool = Form(default=True, description="마크다운 전처리 여부"),
    style_settings: Optional[str] = Form(default=None, description="스타일 설정 (JSON)"),
):
    """
    마크다운을 HWPX로 변환 요청

    파일 업로드 또는 텍스트 직접 입력 중 하나를 선택하여 변환합니다.

    **요청 방식:**
    - `file`: 마크다운 파일 업로드 (multipart/form-data)
    - `markdown`: 마크다운 텍스트 직접 입력

    **응답:**
    - `conversion_id`: 변환 작업 ID (상태 조회 및 다운로드에 사용)
    - `status`: queued → processing → succeeded/failed
    """
    storage = get_storage()

    # 입력 확인
    if file is None and markdown is None:
        raise HTTPException(
            status_code=400, detail="file 또는 markdown 중 하나는 필수입니다."
        )

    # 파일명 결정
    if file is not None:
        input_filename = file.filename or "upload.md"
        content = await file.read()
        markdown_text = content.decode("utf-8")
    else:
        input_filename = f"{filename}.md"
        markdown_text = markdown

    # 작업 생성
    job = storage.create_job(input_filename=input_filename, template_id=template_id)

    try:
        job.mark_processing()
        storage.update_job(job)

        # 입력 파일 저장
        input_path = storage.get_input_path(job.conversion_id, input_filename)
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        job.input_path = str(input_path)
        job.input_size_bytes = len(markdown_text.encode("utf-8"))

        # 출력 경로
        output_path = storage.get_output_path(job.conversion_id, filename)

        # 스타일 설정 파싱
        parsed_style_settings = None
        if style_settings:
            try:
                parsed_style_settings = json.loads(style_settings)
                logger.info(f"Style settings received: {parsed_style_settings}")
            except json.JSONDecodeError:
                logger.warning("Invalid style_settings JSON, using defaults")
        else:
            logger.info("No style_settings received, using defaults")

        # 변환 실행
        converter = HwpxConverter()
        _, processing_time, output_size = converter.convert(
            str(input_path), str(output_path), preprocess=preprocess, style_settings=parsed_style_settings
        )

        # 성공 처리
        job.mark_succeeded(str(output_path), output_size, processing_time)
        storage.update_job(job)

        return ConversionResponse(
            conversion_id=job.conversion_id,
            status=job.status,
            created_at=job.created_at,
            message="변환이 완료되었습니다.",
        )

    except HwpxConverterError as e:
        job.mark_failed(e.code.value, e.message)
        storage.update_job(job)
        raise

    except Exception as e:
        job.mark_failed(ErrorCode.E_CONVERSION_FAILED.value, str(e))
        storage.update_job(job)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/v1/conversions/{conversion_id}",
    response_model=ConversionStatusResponse,
    tags=["변환"],
    summary="변환 상태 조회 (API-02)",
)
async def get_conversion_status(conversion_id: str):
    """
    변환 작업 상태 조회

    **응답:**
    - `status`: 작업 상태 (queued/processing/succeeded/failed)
    - `output_ready`: 다운로드 가능 여부
    - `error_code`, `error_message`: 실패 시 에러 정보
    """
    storage = get_storage()
    job = storage.get_job(conversion_id)

    return ConversionStatusResponse(
        conversion_id=job.conversion_id,
        status=job.status,
        output_ready=job.output_ready(),
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        processing_time_ms=job.processing_time_ms,
    )


@app.get(
    "/v1/conversions/{conversion_id}/download",
    tags=["변환"],
    summary="결과 다운로드 (API-03)",
)
async def download_conversion(conversion_id: str):
    """
    변환된 HWPX 파일 다운로드

    변환이 완료된 후 이 엔드포인트를 통해 결과 파일을 다운로드합니다.
    """
    storage = get_storage()
    job = storage.get_job(conversion_id)

    if job.status != ConversionStatus.SUCCEEDED:
        raise HTTPException(status_code=400, detail="변환이 완료되지 않았습니다.")

    if not job.output_path or not Path(job.output_path).exists():
        raise JobExpiredError(conversion_id)

    return FileResponse(
        path=job.output_path,
        filename=Path(job.output_path).name,
        media_type="application/vnd.hancom.hwpx",
    )


@app.delete(
    "/v1/conversions/{conversion_id}",
    tags=["변환"],
    summary="변환 작업 삭제",
)
async def delete_conversion(conversion_id: str):
    """변환 작업 및 관련 파일 삭제"""
    storage = get_storage()
    success = storage.delete_job(conversion_id)

    if not success:
        raise JobNotFoundError(conversion_id)

    return {"success": True, "message": "삭제되었습니다."}


# ============================================================================
# 템플릿 API (TRD 2.5)
# ============================================================================


@app.get(
    "/v1/templates",
    response_model=TemplateListResponse,
    tags=["템플릿"],
    summary="템플릿 목록 (API-04)",
)
async def list_templates():
    """등록된 템플릿 목록 조회"""
    storage = get_storage()
    templates = storage.list_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                template_id=t.template_id,
                name=t.name,
                version=t.version,
                is_default=t.is_default,
                description=t.description,
                created_at=t.created_at,
            )
            for t in templates
        ],
        total_count=len(templates),
    )


@app.post(
    "/v1/templates",
    response_model=TemplateResponse,
    tags=["템플릿"],
    summary="템플릿 업로드 (API-05)",
)
async def upload_template(
    file: UploadFile = File(..., description="HWPX 템플릿 파일"),
    name: str = Form(..., description="템플릿 이름"),
    version: str = Form(default="1.0.0", description="템플릿 버전"),
    is_default: bool = Form(default=False, description="기본 템플릿 여부"),
    description: Optional[str] = Form(default=None, description="템플릿 설명"),
):
    """
    새 템플릿 업로드

    HWPX 파일을 업로드하여 새 템플릿을 등록합니다.
    업로드 시 샘플 마크다운으로 변환 테스트를 수행합니다.
    """
    storage = get_storage()

    # 파일 확장자 확인
    if not file.filename.endswith(".hwpx"):
        raise HTTPException(status_code=400, detail="HWPX 파일만 업로드 가능합니다.")

    # 템플릿 저장
    template = Template(
        name=name,
        version=version,
        file_path="",  # 임시
        is_default=is_default,
        description=description,
    )

    template_path = storage.templates_dir / f"{template.template_id}.hwpx"

    # 파일 저장
    content = await file.read()
    with open(template_path, "wb") as f:
        f.write(content)

    template.file_path = str(template_path)

    # TODO: 샘플 변환 테스트 (TRD 2.5 API-05)

    # 등록
    storage.register_template(template)

    return TemplateResponse(
        template_id=template.template_id,
        name=template.name,
        version=template.version,
        is_default=template.is_default,
        description=template.description,
        created_at=template.created_at,
    )


# ============================================================================
# 스타일 가이드 API
# ============================================================================


@app.get(
    "/v1/styles",
    response_model=List[StyleInfo],
    tags=["가이드"],
    summary="스타일 정보 조회",
)
async def get_styles():
    """기본 스타일(글머리 기호, 폰트 크기) 정보 조회"""
    return [
        StyleInfo(
            level=1, bullet="□", font_size_pt=13.0, description="1단계 항목 (주요 항목)"
        ),
        StyleInfo(
            level=2, bullet="ㅇ", font_size_pt=12.0, description="2단계 항목 (세부 항목)"
        ),
        StyleInfo(level=3, bullet="-", font_size_pt=11.0, description="3단계 항목 (상세 내용)"),
        StyleInfo(level=4, bullet="·", font_size_pt=10.0, description="4단계 항목"),
    ]


@app.get(
    "/v1/guide",
    tags=["가이드"],
    summary="마크다운 작성 가이드",
)
async def get_markdown_guide():
    """공공기관 보고서용 마크다운 작성 가이드"""
    return {
        "mappings": [
            {"markdown": "# 제목", "hwpx": "Ⅰ. 제목", "description": "대제목 (로마숫자)"},
            {"markdown": "## 제목", "hwpx": "① 제목", "description": "중제목 (동그라미숫자)"},
            {"markdown": "- 항목", "hwpx": "□ 항목", "description": "1단계 (13pt)"},
            {"markdown": "    - 항목", "hwpx": "ㅇ 항목", "description": "2단계 (12pt)"},
            {"markdown": "> 주석", "hwpx": "* 주석", "description": "주석 (10pt)"},
        ],
        "example_input": """# '25년 평가 및 향후 업무추진방향

## '25년 성과 및 보완점

- 교육·돌봄에 대한 **국가책임의 강화**
    - 국가책임형 유아 교육·보육 실현

> '25년 7월부터 만 5세 무상교육·보육 실시
""",
        "notes": [
            "들여쓰기는 4칸 공백으로 합니다.",
            "볼드체는 **텍스트** 형식으로 표시합니다.",
            "특수문자(「」, ~ 등)는 그대로 유지됩니다.",
        ],
    }


# ============================================================================
# ChatGPT 프롬프트 API (PRD FR-01, FR-02)
# ============================================================================


class PromptRequest(BaseModel):
    """프롬프트 생성 요청"""

    topic: str = Field(..., description="문서 주제", min_length=1)


class PromptResponse(BaseModel):
    """프롬프트 응답"""

    prompt: str = Field(..., description="ChatGPT용 프롬프트")
    topic: str = Field(..., description="입력된 주제")
    usage_guide: str = Field(..., description="사용 가이드")


@app.get(
    "/v1/prompt",
    response_model=PromptResponse,
    tags=["프롬프트"],
    summary="ChatGPT 프롬프트 조회",
)
async def get_prompt_template(topic: str = Query(default="", description="문서 주제")):
    """
    ChatGPT용 시스템 프롬프트 조회 (PRD FR-01)

    AI가 Markdown 코드블록 형태로만 응답하도록 하는 프롬프트를 반환합니다.
    """
    topic_text = topic if topic else "(사용자가 입력할 주제)"
    return PromptResponse(
        prompt=CHATGPT_PROMPT_TEMPLATE.format(topic=topic_text),
        topic=topic_text,
        usage_guide="이 프롬프트를 ChatGPT에 복사하여 사용하세요. AI 응답을 그대로 복사하여 웹서비스에 붙여넣으면 됩니다.",
    )


@app.post(
    "/v1/prompt",
    response_model=PromptResponse,
    tags=["프롬프트"],
    summary="ChatGPT 프롬프트 생성",
)
async def create_prompt(request: PromptRequest):
    """
    주제를 입력받아 ChatGPT용 프롬프트 생성 (PRD FR-01)

    사용자가 복사하여 ChatGPT에 바로 사용할 수 있는 프롬프트를 생성합니다.
    """
    return PromptResponse(
        prompt=CHATGPT_PROMPT_TEMPLATE.format(topic=request.topic),
        topic=request.topic,
        usage_guide="이 프롬프트를 ChatGPT에 복사하여 사용하세요. AI 응답을 그대로 복사하여 웹서비스에 붙여넣으면 됩니다.",
    )


# ============================================================================
# 서버 실행
# ============================================================================


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """API 서버 실행"""
    import uvicorn

    print(
        f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║       공공기관 HWPX 변환 서비스 (API Server v1.0)             ║
    ║                                                              ║
    ║  마크다운 → 공공기관 스타일 HWPX 변환                        ║
    ║  Ⅰ. → ① → □ → ㅇ                                           ║
    ║                                                              ║
    ║  웹 UI:    http://localhost:{port}/                          ║
    ║  API 문서: http://localhost:{port}/docs                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    )

    uvicorn.run(
        "hwpx_converter.api:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server(reload=True)
