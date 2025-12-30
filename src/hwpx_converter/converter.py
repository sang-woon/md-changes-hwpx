"""
HWPX 변환기 코어 모듈

마크다운을 공공기관 보고서 스타일의 HWPX로 변환합니다.

서식 계층 구조 (TRD 2.7):
- # 대제목 → Ⅰ. (로마숫자)
- ## 중제목 → ① (동그라미숫자)
- - 1단계 → □ (네모, 13pt)
- - - 2단계 → ㅇ (이응, 12pt)
- > 주석 → * (10pt)
"""

import os
import io
import re
import sys
import json
import time
import shutil
import zipfile
import tempfile
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from .errors import (
    HwpxConverterError,
    PandocNotFoundError,
    ConversionFailedError,
    TemplateInvalidError,
    TemplateNotFoundError,
    InputTooLargeError,
)

# 로깅 설정
logger = logging.getLogger(__name__)


class HwpxConverter:
    """
    공공기관 보고서 스타일 HWPX 변환기

    마크다운을 Ⅰ.→①→□→ㅇ 형태의 공공기관 보고서 스타일로 변환합니다.
    """

    # HWPX XML 네임스페이스
    NAMESPACES = {
        "hh": "http://www.hancom.co.kr/hwpml/2011/head",
        "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
        "hc": "http://www.hancom.co.kr/hwpml/2011/core",
        "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    }

    # 로마 숫자 (대제목)
    ROMAN_NUMERALS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]

    # 동그라미 숫자 (중제목)
    CIRCLED_NUMBERS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

    # 기본 글머리 기호
    DEFAULT_BULLETS = {
        1: "□",  # 1단계: 네모
        2: "ㅇ",  # 2단계: 이응
        3: "-",  # 3단계: 대시
        4: "·",  # 4단계: 점
    }

    # 기본 폰트 크기 (HWP 단위: 1pt = 100)
    DEFAULT_FONT_SIZES = {
        "title": 1800,  # 대제목: 18pt
        "subtitle": 1500,  # 중제목: 15pt
        "level1": 1300,  # 1단계: 13pt
        "level2": 1200,  # 2단계: 12pt
        "note": 1000,  # 주석: 10pt
        "body": 1200,  # 본문: 12pt
    }

    # 최대 입력 크기 (3MB - NFR-01)
    MAX_INPUT_SIZE = 3 * 1024 * 1024

    def __init__(
        self,
        template_path: Optional[str] = None,
        bullets: Optional[Dict[int, str]] = None,
        font_sizes: Optional[Dict[str, int]] = None,
    ):
        """
        변환기 초기화

        Args:
            template_path: 참조 HWPX 템플릿 경로 (None이면 기본 템플릿 사용)
            bullets: 커스텀 글머리 기호 설정
            font_sizes: 커스텀 폰트 크기 설정
        """
        self.template_path = template_path
        self.bullets = bullets or self.DEFAULT_BULLETS.copy()
        self.font_sizes = font_sizes or self.DEFAULT_FONT_SIZES.copy()

        # 카운터 초기화
        self._title_counter = 0
        self._subtitle_counter = 0

        # pypandoc 검증
        self._verify_pandoc()

        # 기본 템플릿 경로 설정
        if self.template_path is None:
            self.template_path = self._find_default_template()

    def _verify_pandoc(self):
        """Pandoc 설치 확인"""
        try:
            import pypandoc

            pypandoc.get_pandoc_version()
        except Exception as e:
            raise PandocNotFoundError(detail=str(e))

    def _find_default_template(self) -> Optional[str]:
        """기본 템플릿 경로 찾기"""
        search_paths = [
            # 패키지 내 템플릿
            Path(__file__).parent / "templates" / "blank.hwpx",
            # 프로젝트 루트
            Path(__file__).parent.parent.parent / "data" / "templates" / "blank.hwpx",
            # docs 폴더
            Path(__file__).parent.parent.parent / "docs" / "blank.hwpx",
            # 시스템 설치
            Path("/usr/local/lib/python3.12/dist-packages/pypandoc_hwpx/blank.hwpx"),
        ]

        for path in search_paths:
            if path.exists():
                logger.debug(f"Found default template: {path}")
                return str(path)

        logger.warning("Default template not found")
        return None

    def _get_roman(self, num: int) -> str:
        """숫자를 로마 숫자로 변환"""
        if 1 <= num <= len(self.ROMAN_NUMERALS):
            return self.ROMAN_NUMERALS[num - 1]
        return str(num)

    def _get_circled(self, num: int) -> str:
        """숫자를 동그라미 숫자로 변환"""
        if 1 <= num <= len(self.CIRCLED_NUMBERS):
            return self.CIRCLED_NUMBERS[num - 1]
        return f"({num})"

    def preprocess_markdown(self, markdown_text: str) -> str:
        """
        마크다운 텍스트를 공공기관 서식에 맞게 전처리

        변환 규칙 (MARKDOWN_GUIDE.md 참조):
        - # 제목 → Ⅰ. 제목 (대제목)
        - ## 제목 → ① 제목 (중제목)
        - - 항목 → □ 항목 (1단계)
        -     - 항목 → ㅇ 항목 (2단계)
        - > 주석 → * 주석
        """
        lines = markdown_text.split("\n")
        result_lines = []

        self._title_counter = 0
        self._subtitle_counter = 0

        for line in lines:
            stripped = line.strip()

            # 대제목: # → Ⅰ.
            if stripped.startswith("# ") and not stripped.startswith("## "):
                self._title_counter += 1
                self._subtitle_counter = 0  # 중제목 카운터 리셋
                title_text = stripped[2:].strip()

                # 이미 로마숫자가 있으면 그대로 사용
                if not any(title_text.startswith(r) for r in self.ROMAN_NUMERALS):
                    result_lines.append(f"# {self._get_roman(self._title_counter)}. {title_text}")
                else:
                    result_lines.append(line)
                continue

            # 중제목: ## → ①
            if stripped.startswith("## "):
                self._subtitle_counter += 1
                subtitle_text = stripped[3:].strip()

                # 이미 동그라미 숫자가 있으면 그대로 사용
                if not any(subtitle_text.startswith(c) for c in self.CIRCLED_NUMBERS):
                    result_lines.append(
                        f"## {self._get_circled(self._subtitle_counter)} {subtitle_text}"
                    )
                else:
                    result_lines.append(line)
                continue

            # 주석: > → *
            if stripped.startswith("> "):
                note_text = stripped[2:].strip()
                if not note_text.startswith("*"):
                    result_lines.append(f"> * {note_text}")
                else:
                    result_lines.append(line)
                continue

            # 리스트 항목: - → □ 또는 ㅇ
            if stripped.startswith("- "):
                indent = len(line) - len(line.lstrip())
                content = stripped[2:].strip()

                if indent >= 4:  # 2단계 (들여쓰기 있음)
                    if not content.startswith("ㅇ"):
                        indent_str = " " * indent
                        result_lines.append(f"{indent_str}- ㅇ {content}")
                    else:
                        result_lines.append(line)
                else:  # 1단계
                    if not content.startswith("□"):
                        result_lines.append(f"- □ {content}")
                    else:
                        result_lines.append(line)
                continue

            # 그 외는 그대로
            result_lines.append(line)

        return "\n".join(result_lines)

    def convert(
        self,
        input_path: str,
        output_path: str,
        preprocess: bool = True,
    ) -> Tuple[str, int, int]:
        """
        마크다운을 공공기관 스타일 HWPX로 변환

        Args:
            input_path: 입력 마크다운 파일 경로
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부

        Returns:
            (출력 파일 경로, 처리 시간(ms), 출력 파일 크기(bytes))

        Raises:
            FileNotFoundError: 입력 파일을 찾을 수 없을 때
            TemplateNotFoundError: 템플릿을 찾을 수 없을 때
            InputTooLargeError: 입력 파일이 너무 클 때
            ConversionFailedError: 변환 실패 시
        """
        start_time = time.time()

        # 입력 파일 확인
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

        # 파일 크기 확인
        input_size = input_file.stat().st_size
        if input_size > self.MAX_INPUT_SIZE:
            raise InputTooLargeError(input_size, self.MAX_INPUT_SIZE)

        # 템플릿 확인
        if self.template_path is None or not Path(self.template_path).exists():
            raise TemplateNotFoundError()

        try:
            # 마크다운 파일 읽기
            with open(input_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()

            # 전처리 적용
            if preprocess:
                markdown_text = self.preprocess_markdown(markdown_text)
                logger.debug("Preprocessed markdown applied")

            # 임시 파일에 전처리된 마크다운 저장
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(markdown_text)
                tmp_path = tmp.name

            try:
                # pypandoc-hwpx로 변환
                from pypandoc_hwpx.PandocToHwpx import PandocToHwpx

                PandocToHwpx.convert_to_hwpx(tmp_path, output_path, self.template_path)

            finally:
                # 임시 파일 삭제
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # 결과 확인
            output_file = Path(output_path)
            if not output_file.exists():
                raise ConversionFailedError(detail="Output file was not created")

            output_size = output_file.stat().st_size
            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Conversion completed: {input_path} -> {output_path} "
                f"({processing_time_ms}ms, {output_size} bytes)"
            )

            return output_path, processing_time_ms, output_size

        except HwpxConverterError:
            raise
        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            raise ConversionFailedError(detail=str(e))

    def convert_text(
        self,
        markdown_text: str,
        output_path: str,
        preprocess: bool = True,
    ) -> Tuple[str, int, int]:
        """
        마크다운 텍스트를 직접 변환

        Args:
            markdown_text: 마크다운 텍스트
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부

        Returns:
            (출력 파일 경로, 처리 시간(ms), 출력 파일 크기(bytes))
        """
        # 크기 확인
        input_size = len(markdown_text.encode("utf-8"))
        if input_size > self.MAX_INPUT_SIZE:
            raise InputTooLargeError(input_size, self.MAX_INPUT_SIZE)

        # 임시 파일에 마크다운 저장
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(markdown_text)
            tmp_path = tmp.name

        try:
            return self.convert(tmp_path, output_path, preprocess)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# 마크다운 서식 가이드 (CLI 출력용)
MARKDOWN_GUIDE = """
╔════════════════════════════════════════════════════════════════════╗
║              공공기관 보고서 마크다운 작성 가이드                    ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  마크다운 입력              →    HWPX 출력                          ║
║  ─────────────────────────────────────────────────────────────     ║
║                                                                    ║
║  # 대제목                   →    Ⅰ. 대제목 (파란 배경)              ║
║  ## 중제목                  →    ① 중제목 (파란 밑줄)               ║
║  - 1단계 항목               →    □ 1단계 항목 (13pt 볼드)           ║
║      - 2단계 항목           →    ㅇ 2단계 항목 (12pt)               ║
║  > 주석 내용                →    * 주석 내용 (10pt)                 ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
"""


def convert_markdown_to_hwpx(
    input_path: str,
    output_path: str,
    template_path: Optional[str] = None,
    preprocess: bool = True,
) -> str:
    """
    간편 변환 함수

    Args:
        input_path: 입력 마크다운 파일
        output_path: 출력 HWPX 파일
        template_path: 참조 템플릿 (선택)
        preprocess: 전처리 여부

    Returns:
        생성된 파일 경로
    """
    converter = HwpxConverter(template_path=template_path)
    result_path, _, _ = converter.convert(input_path, output_path, preprocess)
    return result_path
