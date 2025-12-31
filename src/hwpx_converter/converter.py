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
        "level1": 1500,  # 1단계: 15pt
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

    def _postprocess_fonts(self, hwpx_path: str, style_settings: Dict[str, Any]) -> None:
        """
        HWPX 파일에 글꼴 크기 및 글꼴 후처리 적용

        Args:
            hwpx_path: HWPX 파일 경로
            style_settings: 글꼴 크기 및 글꼴 설정
        """
        # 글꼴 크기 추출 (pt 단위 → HWP 단위: 1pt = 100)
        font_sizes = {
            'title': style_settings.get('title', {}).get('size', 18) * 100,
            'subtitle': style_settings.get('subtitle', {}).get('size', 15) * 100,
            'level1': style_settings.get('level1', {}).get('size', 14) * 100,
            'level2': style_settings.get('level2', {}).get('size', 12) * 100,
            'note': style_settings.get('note', {}).get('size', 12) * 100,
        }

        # bold 설정
        bold_settings = {
            'title': style_settings.get('title', {}).get('bold', True),
            'subtitle': style_settings.get('subtitle', {}).get('bold', True),
            'level1': style_settings.get('level1', {}).get('bold', False),
            'level2': style_settings.get('level2', {}).get('bold', False),
            'note': style_settings.get('note', {}).get('bold', False),
        }

        # 글꼴 설정
        font_names = {
            'title': style_settings.get('title', {}).get('font', '함초롬바탕'),
            'subtitle': style_settings.get('subtitle', {}).get('font', '함초롬바탕'),
            'level1': style_settings.get('level1', {}).get('font', '함초롬바탕'),
            'level2': style_settings.get('level2', {}).get('font', '함초롬바탕'),
            'note': style_settings.get('note', {}).get('font', '함초롬바탕'),
        }

        logger.info(f"Font postprocessing: sizes={font_sizes}, fonts={font_names}")

        # 임시 파일로 후처리
        temp_path = hwpx_path + '.tmp'

        # charPr ID 매핑
        self._char_pr_id_map = {}
        self._max_char_pr_id = 10
        self._font_id_map = {}  # 글꼴 ID 매핑
        self._max_font_id = 2   # 기존 폰트 ID 다음부터 시작

        # 먼저 header.xml 파싱하여 기존 charPr ID 및 font ID 확인
        with zipfile.ZipFile(hwpx_path, 'r') as zin:
            header_xml = zin.read('Contents/header.xml').decode('utf-8')
            self._parse_header_for_char_pr_ids(header_xml)
            self._parse_header_for_font_ids(header_xml)

        # HWPX 파일 수정
        with zipfile.ZipFile(hwpx_path, 'r') as zin:
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    content = zin.read(item.filename)

                    if item.filename == 'Contents/header.xml':
                        # 헤더에 폰트 및 charPr 스타일 추가
                        header_xml = content.decode('utf-8')
                        modified_header = self._add_fonts_to_header(header_xml, font_names)
                        modified_header = self._add_char_pr_styles(modified_header, font_sizes, bold_settings, font_names)
                        zout.writestr(item, modified_header.encode('utf-8'))

                    elif item.filename == 'Contents/section0.xml':
                        # 섹션에 글꼴 적용
                        section_xml = content.decode('utf-8')
                        modified_section = self._apply_fonts_to_section(section_xml)
                        zout.writestr(item, modified_section.encode('utf-8'))

                    else:
                        zout.writestr(item, content)

        # 원본 파일 교체
        os.replace(temp_path, hwpx_path)
        logger.info("Font postprocessing completed")

    def _parse_header_for_char_pr_ids(self, header_xml: str) -> None:
        """헤더에서 charPr ID 파싱"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return

        # charProperties에서 마지막 ID 찾기
        char_props = root.find('.//hh:charProperties', self.NAMESPACES)
        if char_props is not None:
            self._max_char_pr_id = int(char_props.get('itemCnt', '10'))

    def _parse_header_for_font_ids(self, header_xml: str) -> None:
        """헤더에서 font ID 파싱"""
        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return

        # fontfaces에서 마지막 font ID 찾기
        fontface = root.find('.//hh:fontface[@lang="HANGUL"]', self.NAMESPACES)
        if fontface is not None:
            font_cnt = int(fontface.get('fontCnt', '2'))
            self._max_font_id = font_cnt

    def _add_fonts_to_header(self, header_xml: str, font_names: Dict[str, str]) -> str:
        """헤더에 사용자 정의 폰트 추가"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return header_xml

        # 사용할 고유 폰트 목록 추출
        unique_fonts = set(font_names.values())

        # 각 언어별 fontface에 폰트 추가
        languages = ['HANGUL', 'LATIN', 'HANJA', 'JAPANESE', 'OTHER', 'SYMBOL', 'USER']

        for lang in languages:
            fontface = root.find(f'.//hh:fontface[@lang="{lang}"]', self.NAMESPACES)
            if fontface is None:
                continue

            current_font_cnt = int(fontface.get('fontCnt', '0'))

            for font_name in unique_fonts:
                # 이미 등록된 폰트인지 확인
                existing = fontface.find(f'.//hh:font[@face="{font_name}"]', self.NAMESPACES)
                if existing is not None:
                    self._font_id_map[font_name] = existing.get('id')
                    continue

                # 새 폰트 추가
                font_id = str(current_font_cnt)
                self._font_id_map[font_name] = font_id

                font_elem = ET.SubElement(fontface, '{http://www.hancom.co.kr/hwpml/2011/head}font')
                font_elem.set('id', font_id)
                font_elem.set('face', font_name)
                font_elem.set('type', 'TTF')
                font_elem.set('isEmbedded', '0')

                current_font_cnt += 1

            fontface.set('fontCnt', str(current_font_cnt))

        return ET.tostring(root, encoding='unicode')

    def _add_char_pr_styles(self, header_xml: str, font_sizes: Dict[str, int], bold_settings: Dict[str, bool], font_names: Dict[str, str] = None) -> str:
        """헤더에 charPr 스타일 추가"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return header_xml

        char_props = root.find('.//hh:charProperties', self.NAMESPACES)
        if char_props is None:
            return header_xml

        current_id = self._max_char_pr_id

        # 각 레벨별 charPr 추가
        for level_name in ['title', 'subtitle', 'level1', 'level2', 'note']:
            height = font_sizes.get(level_name, 1200)
            bold = bold_settings.get(level_name, False)

            # 폰트 ID 가져오기
            font_id = '0'  # 기본 폰트
            if font_names and level_name in font_names:
                font_name = font_names[level_name]
                font_id = self._font_id_map.get(font_name, '0')

            char_pr = ET.SubElement(char_props, '{http://www.hancom.co.kr/hwpml/2011/head}charPr')
            char_pr.set('id', str(current_id))
            char_pr.set('height', str(int(height)))
            char_pr.set('textColor', '#000000')
            char_pr.set('shadeColor', 'none')
            char_pr.set('useFontSpace', '0')
            char_pr.set('useKerning', '0')
            char_pr.set('symMark', 'NONE')
            char_pr.set('borderFillIDRef', '2')
            if bold:
                char_pr.set('bold', '1')

            # fontRef - 사용자 지정 폰트 ID 사용
            font_ref = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}fontRef')
            font_ref.set('hangul', font_id)
            font_ref.set('latin', font_id)
            font_ref.set('hanja', font_id)
            font_ref.set('japanese', font_id)
            font_ref.set('other', font_id)
            font_ref.set('symbol', font_id)
            font_ref.set('user', font_id)

            # ratio
            ratio = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}ratio')
            for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
                ratio.set(lang, '100')

            # spacing
            spacing = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}spacing')
            for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
                spacing.set(lang, '0')

            # relSz
            rel_sz = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}relSz')
            for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
                rel_sz.set(lang, '100')

            # offset
            offset = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}offset')
            for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
                offset.set(lang, '0')

            # underline
            underline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}underline')
            underline.set('type', 'NONE')
            underline.set('shape', 'SOLID')
            underline.set('color', '#000000')

            # strikeout
            strikeout = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}strikeout')
            strikeout.set('shape', 'NONE')
            strikeout.set('color', '#000000')

            # outline
            outline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}outline')
            outline.set('type', 'NONE')

            # shadow
            shadow = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}shadow')
            shadow.set('type', 'NONE')
            shadow.set('color', '#C0C0C0')
            shadow.set('offsetX', '5')
            shadow.set('offsetY', '5')

            self._char_pr_id_map[level_name] = str(current_id)
            current_id += 1

        char_props.set('itemCnt', str(current_id))

        return ET.tostring(root, encoding='unicode')

    def _apply_fonts_to_section(self, section_xml: str) -> str:
        """섹션 XML에 글꼴 적용 및 레벨 마커 제거"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(section_xml)
        except ET.ParseError:
            return section_xml

        # 모든 paragraph 찾기
        for para in root.findall('.//hp:p', self.NAMESPACES):
            # 텍스트 내용 확인
            text_content = ''
            for run in para.findall('.//hp:run', self.NAMESPACES):
                for t in run.findall('.//hp:t', self.NAMESPACES):
                    if t.text:
                        text_content += t.text

            # 레벨 판별
            level = self._determine_level(text_content)
            char_pr_id = self._char_pr_id_map.get(level, '0')

            # 모든 run의 charPrIDRef 수정 및 마커 제거
            for run in para.findall('.//hp:run', self.NAMESPACES):
                run.set('charPrIDRef', char_pr_id)

                # 텍스트에서 레벨 마커 제거
                for t in run.findall('.//hp:t', self.NAMESPACES):
                    if t.text:
                        for marker in self.LEVEL_MARKERS.values():
                            t.text = t.text.replace(marker, '')

        return ET.tostring(root, encoding='unicode')

    def _determine_level(self, text: str) -> str:
        """텍스트 내용에 따른 레벨 결정 (마커 기반)"""
        text = text.strip()

        # 레벨 마커로 판별 (가장 우선)
        for level, marker in self.LEVEL_MARKERS.items():
            if marker in text:
                return level

        # 마커가 없는 경우 기존 방식으로 fallback
        # 대제목 (Ⅰ. Ⅱ. 등)
        if any(text.startswith(r + '.') for r in self.ROMAN_NUMERALS):
            return 'title'

        # 중제목 (① ② 등)
        if any(text.startswith(c) for c in self.CIRCLED_NUMBERS):
            return 'subtitle'

        # 1단계 (□)
        if text.startswith('□') or text.lstrip('\u00A0').startswith('□'):
            return 'level1'

        # 2단계 (ㅇ)
        if text.startswith('ㅇ') or text.lstrip('\u00A0').startswith('ㅇ'):
            return 'level2'

        # 주석 (*)
        if text.startswith('*') or text.lstrip('\u00A0').startswith('*'):
            return 'note'

        # 기본값: body
        return 'level1'

    # 레벨 마커 (후처리에서 글꼴 적용 시 사용)
    LEVEL_MARKERS = {
        'title': '⟦T⟧',
        'subtitle': '⟦S⟧',
        'level1': '⟦1⟧',
        'level2': '⟦2⟧',
        'note': '⟦N⟧',
    }

    def preprocess_markdown(self, markdown_text: str, style_settings: Optional[Dict[str, Any]] = None) -> str:
        """
        마크다운 텍스트를 공공기관 서식에 맞게 전처리 (일반 텍스트로 변환)

        매핑 정보(mappings)가 있으면 동적으로 적용하고,
        없으면 기본 규칙 사용:
        - # 제목 → Ⅰ. 제목 (대제목)
        - ## 제목 → ① 제목 (중제목)
        - - 항목 → □ 항목 (1단계)
        -     - 항목 → ㅇ 항목 (2단계)
        - > 주석 → * 주석

        각 레벨에 마커(⟦T⟧, ⟦S⟧, ⟦1⟧, ⟦2⟧, ⟦N⟧)를 추가하여
        후처리 시 글꼴 적용에 사용합니다.
        """
        # Non-breaking space (NBSP, U+00A0) - Pandoc이 제거하지 않는 공백
        NBSP = '\u00A0'

        # 스타일 설정에서 글머리 기호 및 칸 띄우기(indent) 추출
        title_bullet_style = "roman"  # roman, number, none
        subtitle_bullet_style = "circled"  # circled, number, korean, none
        level1_bullet = "□"
        level2_bullet = "ㅇ"
        note_bullet = "*"
        level1_indent = 1  # 1단계 앞 칸 띄우기 (기본 1칸)
        level2_indent = 3  # 2단계 앞 칸 띄우기 (기본 3칸)

        # 매핑 정보 (마크다운 요소 → HWPX 스타일)
        mappings = {}

        if style_settings:
            if "title" in style_settings:
                title_bullet_style = style_settings["title"].get("bullet", "roman")
            if "subtitle" in style_settings:
                subtitle_bullet_style = style_settings["subtitle"].get("bullet", "circled")
            if "level1" in style_settings:
                level1_bullet = style_settings["level1"].get("bullet", "□")
                level1_indent = style_settings["level1"].get("indent", 1)
            if "level2" in style_settings:
                level2_bullet = style_settings["level2"].get("bullet", "ㅇ")
                level2_indent = style_settings["level2"].get("indent", 3)
            if "note" in style_settings:
                note_bullet = style_settings["note"].get("bullet", "*")
            if "mappings" in style_settings:
                mappings = style_settings["mappings"]

        logger.info(f"Style settings applied: level1_bullet={level1_bullet}, level1_indent={level1_indent}, level2_bullet={level2_bullet}, level2_indent={level2_indent}")
        logger.info(f"Mappings: {mappings}")

        # 한글 글머리 기호
        korean_chars = ["가", "나", "다", "라", "마", "바", "사", "아", "자", "차"]

        lines = markdown_text.split("\n")
        result_lines = []

        self._title_counter = 0
        self._subtitle_counter = 0

        def get_mapped_style(md_key: str) -> str:
            """마크다운 키에 해당하는 HWPX 스타일 반환"""
            if mappings:
                return mappings.get(md_key, "none")
            # 기본 매핑 (매핑 정보 없을 때)
            defaults = {
                'h1': 'title', 'h2': 'subtitle', 'h3': 'subtitle',
                'h4': 'level1', 'h5': 'level2', 'h6': 'level2',
                'list_0': 'level1', 'list_1': 'level2',
                'quote': 'note'
            }
            return defaults.get(md_key, "none")

        def apply_style(content: str, hwpx_style: str) -> str:
            """HWPX 스타일 적용하여 변환된 텍스트 반환 (레벨 마커 포함)"""
            nonlocal self
            content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)  # 볼드 제거

            # 레벨 마커 가져오기
            marker = self.LEVEL_MARKERS.get(hwpx_style, '')

            if hwpx_style == "title":
                self._title_counter += 1
                self._subtitle_counter = 0
                if not any(content.startswith(r) for r in self.ROMAN_NUMERALS):
                    if title_bullet_style == "roman":
                        return f"{marker}{self._get_roman(self._title_counter)}. {content}"
                    elif title_bullet_style == "number":
                        return f"{marker}{self._title_counter}. {content}"
                return f"{marker}{content}"

            elif hwpx_style == "subtitle":
                self._subtitle_counter += 1
                if not any(content.startswith(c) for c in self.CIRCLED_NUMBERS):
                    if subtitle_bullet_style == "circled":
                        return f"{marker}{self._get_circled(self._subtitle_counter)} {content}"
                    elif subtitle_bullet_style == "number":
                        return f"{marker}{self._subtitle_counter}) {content}"
                    elif subtitle_bullet_style == "korean":
                        korean_char = korean_chars[self._subtitle_counter - 1] if self._subtitle_counter <= len(korean_chars) else str(self._subtitle_counter)
                        return f"{marker}{korean_char}. {content}"
                return f"{marker}{content}"

            elif hwpx_style == "level1":
                spacing = NBSP * level1_indent
                return f"{marker}{spacing}{level1_bullet} {content}"

            elif hwpx_style == "level2":
                spacing = NBSP * level2_indent
                return f"{marker}{spacing}{level2_bullet} {content}"

            elif hwpx_style == "note":
                if note_bullet != "none":
                    return f"{marker}{note_bullet} {content}"
                return f"{marker}{content}"

            else:  # none 또는 기타
                return content

        for line in lines:
            stripped = line.strip()

            # 빈 줄은 그대로
            if not stripped:
                result_lines.append("")
                continue

            # 헤딩 레벨별 처리 (h1 ~ h6)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                hashes = heading_match.group(1)
                content = heading_match.group(2).strip()
                level = len(hashes)
                md_key = f"h{level}"
                hwpx_style = get_mapped_style(md_key)

                if hwpx_style != "none":
                    result_lines.append(apply_style(content, hwpx_style))
                else:
                    result_lines.append(re.sub(r'\*\*(.+?)\*\*', r'\1', content))
                continue

            # 주석: > → note 스타일
            if stripped.startswith("> "):
                content = stripped[2:].strip()
                hwpx_style = get_mapped_style("quote")

                if hwpx_style != "none":
                    result_lines.append(apply_style(content, hwpx_style))
                else:
                    result_lines.append(re.sub(r'\*\*(.+?)\*\*', r'\1', content))
                continue

            # 리스트 항목: - 또는 *
            if stripped.startswith("- ") or stripped.startswith("* "):
                md_indent = len(line) - len(line.lstrip())
                content = stripped[2:].strip()

                # 들여쓰기 레벨 계산 (0, 2, 4... 기준)
                list_level = md_indent // 2
                md_key = f"list_{list_level}"
                hwpx_style = get_mapped_style(md_key)

                if hwpx_style != "none":
                    result_lines.append(apply_style(content, hwpx_style))
                else:
                    result_lines.append(re.sub(r'\*\*(.+?)\*\*', r'\1', content))
                result_lines.append("")  # Pandoc을 위한 빈 줄
                continue

            # 그 외 일반 텍스트 (볼드 처리 제거)
            plain_text = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
            result_lines.append(plain_text)

        # 연속된 빈 줄 정리 (최대 1개로)
        cleaned_lines = []
        prev_empty = False
        for line in result_lines:
            if line == "":
                if not prev_empty:
                    cleaned_lines.append(line)
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False

        return "\n".join(cleaned_lines)

    def convert(
        self,
        input_path: str,
        output_path: str,
        preprocess: bool = True,
        style_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int, int]:
        """
        마크다운을 공공기관 스타일 HWPX로 변환

        Args:
            input_path: 입력 마크다운 파일 경로
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부
            style_settings: 사용자 정의 스타일 설정 (글머리 기호 등)

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
                markdown_text = self.preprocess_markdown(markdown_text, style_settings)
                logger.debug("Preprocessed markdown applied with style settings")

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

                # 글꼴 크기 후처리 적용
                if style_settings:
                    self._postprocess_fonts(output_path, style_settings)
                    logger.debug("Font size post-processing applied")

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
        style_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int, int]:
        """
        마크다운 텍스트를 직접 변환

        Args:
            markdown_text: 마크다운 텍스트
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부
            style_settings: 사용자 정의 스타일 설정

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
            return self.convert(tmp_path, output_path, preprocess, style_settings)
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
