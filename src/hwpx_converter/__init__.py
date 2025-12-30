"""
HWPX Converter - Markdown to HWPX conversion for Korean public agency documents

이 패키지는 마크다운 문서를 공공기관 보고서 스타일의 HWPX 파일로 변환합니다.

주요 기능:
- 공공기관 표준 서식 자동 적용 (Ⅰ.→①→□→ㅇ)
- 레벨별 폰트 크기 자동 설정
- 참조 템플릿 지원
- REST API 서비스

사용 예시:
    from hwpx_converter import HwpxConverter

    converter = HwpxConverter()
    converter.convert('report.md', 'report.hwpx')
"""

__version__ = "1.0.0"
__author__ = "경기도의회 AI입법혁신팀"

from .converter import HwpxConverter
from .errors import (
    HwpxConverterError,
    PandocNotFoundError,
    ConversionFailedError,
    TemplateInvalidError,
    InputTooLargeError,
    UnsupportedMarkdownError,
)
from .models import ConversionJob, Template, ConversionStatus

__all__ = [
    "HwpxConverter",
    "HwpxConverterError",
    "PandocNotFoundError",
    "ConversionFailedError",
    "TemplateInvalidError",
    "InputTooLargeError",
    "UnsupportedMarkdownError",
    "ConversionJob",
    "Template",
    "ConversionStatus",
]
