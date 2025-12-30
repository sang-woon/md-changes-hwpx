#!/usr/bin/env python3
"""
FastAPI 기반 마크다운 → 공공기관 스타일 HWPX 변환 서비스

이 모듈은 REST API를 통해 마크다운 파일을 공공기관 보고서 스타일의
HWPX 파일로 변환하는 웹 서비스를 제공합니다.

주요 기능:
- 마크다운 텍스트 → HWPX 변환
- 마크다운 파일 업로드 → HWPX 다운로드
- 커스텀 글머리 기호/폰트 크기 설정
- HWPX → 마크다운 역변환 (추후)

실행 방법:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import io
import uuid
import tempfile
import shutil
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 변환기 임포트
try:
    from official_converter import OfficialHwpxConverter, convert_md_to_official_hwpx
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from official_converter import OfficialHwpxConverter, convert_md_to_official_hwpx


# FastAPI 앱 초기화
app = FastAPI(
    title="공공기관 HWPX 변환 서비스",
    description="""
    마크다운 문서를 경기도의회 등 공공기관의 보고서 스타일에 맞는 
    HWPX(한글 문서) 파일로 변환하는 API 서비스입니다.
    
    ## 주요 기능
    
    * **텍스트 변환**: 마크다운 텍스트를 직접 입력하여 HWPX로 변환
    * **파일 변환**: 마크다운 파일을 업로드하여 HWPX로 변환
    * **커스텀 스타일**: 글머리 기호, 폰트 크기 등 커스터마이징 지원
    
    ## 글머리 기호 스타일
    
    * Level 1: □ (15pt)
    * Level 2: ○ (13pt)
    * Level 3: - (11pt)
    """,
    version="1.0.0",
    contact={
        "name": "경기도의회 AI입법혁신팀",
        "email": "ai-innovation@ggc.go.kr"
    }
)

# CORS 설정 (개발용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 임시 파일 디렉토리
TEMP_DIR = Path(tempfile.gettempdir()) / "hwpx_converter"
TEMP_DIR.mkdir(exist_ok=True)


# ============================================================================
# Pydantic 모델
# ============================================================================

class ConvertTextRequest(BaseModel):
    """텍스트 변환 요청 모델"""
    markdown: str = Field(..., description="변환할 마크다운 텍스트")
    filename: str = Field(default="output", description="출력 파일명 (확장자 제외)")
    bullets: Optional[Dict[int, str]] = Field(
        default=None,
        description="커스텀 글머리 기호 (레벨: 기호). 예: {1: '□', 2: '○'}"
    )
    font_sizes: Optional[Dict[int, int]] = Field(
        default=None,
        description="커스텀 폰트 크기 (레벨: HWP 단위). 예: {1: 1500, 2: 1300}"
    )


class ConvertTextResponse(BaseModel):
    """텍스트 변환 응답 모델"""
    success: bool
    message: str
    download_url: Optional[str] = None
    file_id: Optional[str] = None


class StyleInfo(BaseModel):
    """스타일 정보 모델"""
    level: int
    bullet: str
    font_size_pt: float
    description: str


class StyleListResponse(BaseModel):
    """스타일 목록 응답 모델"""
    styles: List[StyleInfo]


# ============================================================================
# API 엔드포인트
# ============================================================================

@app.get("/", response_class=JSONResponse)
async def root():
    """서비스 상태 확인"""
    return {
        "service": "공공기관 HWPX 변환 서비스",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "convert_text": "/api/convert/text",
            "convert_file": "/api/convert/file",
            "download": "/api/download/{file_id}",
            "styles": "/api/styles"
        }
    }


@app.get("/api/styles", response_model=StyleListResponse)
async def get_styles():
    """
    기본 스타일 목록 조회
    
    공공기관 보고서에서 사용되는 기본 글머리 기호와 폰트 크기 정보를 반환합니다.
    """
    converter = OfficialHwpxConverter()
    styles = []
    
    descriptions = {
        1: "1단계 항목 (주요 항목)",
        2: "2단계 항목 (세부 항목)",
        3: "3단계 항목 (상세 내용)",
        4: "4단계 항목",
        5: "5단계 항목",
        6: "6단계 항목",
        7: "7단계 항목",
    }
    
    for level in range(1, 8):
        styles.append(StyleInfo(
            level=level,
            bullet=converter.bullets.get(level, '•'),
            font_size_pt=converter.font_sizes.get(level, 1000) / 100,
            description=descriptions.get(level, f"{level}단계 항목")
        ))
    
    return StyleListResponse(styles=styles)


@app.post("/api/convert/text", response_model=ConvertTextResponse)
async def convert_text(request: ConvertTextRequest):
    """
    마크다운 텍스트를 HWPX로 변환
    
    마크다운 텍스트를 직접 입력받아 공공기관 스타일의 HWPX 파일로 변환합니다.
    
    **사용 예시:**
    ```json
    {
        "markdown": "# 제목\\n\\n- 첫 번째 항목\\n    - 세부 항목",
        "filename": "report",
        "bullets": {"1": "□", "2": "○"},
        "font_sizes": {"1": 1500, "2": 1300}
    }
    ```
    """
    try:
        # 고유 파일 ID 생성
        file_id = str(uuid.uuid4())[:8]
        
        # 임시 파일 경로 생성
        input_path = TEMP_DIR / f"{file_id}_input.md"
        output_path = TEMP_DIR / f"{file_id}_{request.filename}.hwpx"
        
        # 마크다운 파일 저장
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(request.markdown)
        
        # 변환기 초기화
        converter = OfficialHwpxConverter(
            bullets=request.bullets,
            font_sizes=request.font_sizes
        )
        
        # 변환 실행
        result_path = converter.convert(str(input_path), str(output_path))
        
        # 임시 입력 파일 삭제
        input_path.unlink(missing_ok=True)
        
        return ConvertTextResponse(
            success=True,
            message="변환이 완료되었습니다.",
            download_url=f"/api/download/{file_id}_{request.filename}",
            file_id=f"{file_id}_{request.filename}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/convert/file")
async def convert_file(
    file: UploadFile = File(..., description="마크다운 파일"),
    bullets_1: str = Form(default="□", description="Level 1 글머리 기호"),
    bullets_2: str = Form(default="○", description="Level 2 글머리 기호"),
    font_size_1: int = Form(default=1500, description="Level 1 폰트 크기 (HWP 단위)"),
    font_size_2: int = Form(default=1300, description="Level 2 폰트 크기 (HWP 단위)"),
):
    """
    마크다운 파일을 업로드하여 HWPX로 변환
    
    마크다운 파일(.md)을 업로드하면 공공기관 스타일의 HWPX 파일로 변환합니다.
    """
    # 파일 확장자 확인
    if not file.filename.endswith(('.md', '.markdown', '.txt')):
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 파일 형식입니다. .md, .markdown, .txt 파일만 지원됩니다."
        )
    
    try:
        # 고유 파일 ID 생성
        file_id = str(uuid.uuid4())[:8]
        base_name = Path(file.filename).stem
        
        # 임시 파일 경로 생성
        input_path = TEMP_DIR / f"{file_id}_input.md"
        output_path = TEMP_DIR / f"{file_id}_{base_name}.hwpx"
        
        # 업로드된 파일 저장
        content = await file.read()
        with open(input_path, 'wb') as f:
            f.write(content)
        
        # 커스텀 설정
        bullets = {1: bullets_1, 2: bullets_2}
        font_sizes = {1: font_size_1, 2: font_size_2}
        
        # 변환기 초기화 및 변환
        converter = OfficialHwpxConverter(
            bullets=bullets,
            font_sizes=font_sizes
        )
        converter.convert(str(input_path), str(output_path))
        
        # 임시 입력 파일 삭제
        input_path.unlink(missing_ok=True)
        
        return JSONResponse({
            "success": True,
            "message": "변환이 완료되었습니다.",
            "download_url": f"/api/download/{file_id}_{base_name}",
            "file_id": f"{file_id}_{base_name}",
            "original_filename": file.filename
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """
    변환된 HWPX 파일 다운로드
    
    변환 후 발급된 file_id를 사용하여 HWPX 파일을 다운로드합니다.
    """
    file_path = TEMP_DIR / f"{file_id}.hwpx"
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="파일을 찾을 수 없습니다. 파일이 만료되었거나 ID가 잘못되었습니다."
        )
    
    return FileResponse(
        path=str(file_path),
        filename=f"{file_id}.hwpx",
        media_type="application/vnd.hancom.hwpx"
    )


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str):
    """
    임시 파일 삭제
    
    더 이상 필요하지 않은 변환 파일을 수동으로 삭제합니다.
    """
    file_path = TEMP_DIR / f"{file_id}.hwpx"
    
    if file_path.exists():
        file_path.unlink()
        return {"success": True, "message": "파일이 삭제되었습니다."}
    else:
        return {"success": False, "message": "파일을 찾을 수 없습니다."}


# ============================================================================
# 유틸리티 함수
# ============================================================================

def cleanup_old_files(max_age_hours: int = 24):
    """오래된 임시 파일 정리"""
    import time
    
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for file_path in TEMP_DIR.glob("*.hwpx"):
        if now - file_path.stat().st_mtime > max_age_seconds:
            file_path.unlink(missing_ok=True)


# ============================================================================
# 실행
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║       공공기관 HWPX 변환 서비스 (API Server)                 ║
    ║                                                              ║
    ║  마크다운 → 공공기관 스타일 HWPX 변환                        ║
    ║  □ (15pt) → ○ (13pt) → - (11pt)                             ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
