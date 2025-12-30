"""
글꼴 설정이 포함된 HWPX 변환기

글꼴 설정:
- 대제목 (Ⅰ.): HY헤드라인M
- 중제목 (①): 함초롱바탕 굵게 15pt
- 1단계 (□): 함초롱바탕 15pt
- 2단계 (ㅇ): 함초롱바탕 14pt
- 주석 (*): 맑은 고딕
"""

import os
import io
import re
import json
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Tuple

import pypandoc


class FontConfig:
    """글꼴 설정"""

    # 글꼴 정의
    FONTS = {
        'headline': 'HY헤드라인M',
        'hamchorong': '함초롱바탕',
        'malgun': '맑은 고딕',
    }

    # 레벨별 글꼴 설정 (font_key, size_pt, bold)
    LEVEL_FONTS = {
        'title': ('headline', 18, True),      # 대제목: HY헤드라인M 18pt 굵게
        'subtitle': ('hamchorong', 15, True), # 중제목: 함초롱바탕 15pt 굵게
        'level1': ('hamchorong', 15, False),  # 1단계: 함초롱바탕 15pt
        'level2': ('hamchorong', 14, False),  # 2단계: 함초롱바탕 14pt
        'note': ('malgun', 10, False),        # 주석: 맑은 고딕 10pt
    }


class OfficialFontConverter:
    """
    공공기관 스타일 + 글꼴 설정 HWPX 변환기
    """

    NAMESPACES = {
        'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
    }

    # 로마 숫자 (대제목)
    ROMAN_NUMERALS = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ']

    # 동그라미 숫자 (중제목)
    CIRCLED_NUMBERS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path
        self._title_counter = 0
        self._subtitle_counter = 0

        # 기본 템플릿 찾기
        if self.template_path is None:
            search_paths = [
                Path(__file__).parent.parent.parent / 'data' / 'templates' / 'blank.hwpx',
                Path(__file__).parent.parent.parent / 'docs' / 'blank.hwpx',
            ]
            for p in search_paths:
                if p.exists():
                    self.template_path = str(p)
                    break

    def _get_roman(self, num: int) -> str:
        if 1 <= num <= len(self.ROMAN_NUMERALS):
            return self.ROMAN_NUMERALS[num - 1]
        return str(num)

    def _get_circled(self, num: int) -> str:
        if 1 <= num <= len(self.CIRCLED_NUMBERS):
            return self.CIRCLED_NUMBERS[num - 1]
        return f"({num})"

    def preprocess_markdown(self, markdown_text: str) -> str:
        """마크다운 전처리 - 공공기관 서식 적용 (스페이스 기반)

        각 항목이 별도의 paragraph가 되도록 빈 줄 추가
        """
        lines = markdown_text.split('\n')
        result_lines = []

        self._title_counter = 0
        self._subtitle_counter = 0

        for line in lines:
            stripped = line.strip()

            # 빈 줄은 그대로 유지
            if not stripped:
                result_lines.append('')
                continue

            # 대제목: # → Ⅰ.
            if stripped.startswith('# ') and not stripped.startswith('## '):
                self._title_counter += 1
                self._subtitle_counter = 0
                title_text = stripped[2:].strip()
                if not any(title_text.startswith(r) for r in self.ROMAN_NUMERALS):
                    result_lines.append(f"{self._get_roman(self._title_counter)}. {title_text}")
                else:
                    result_lines.append(stripped[2:])
                result_lines.append('')  # 빈 줄 추가로 별도 paragraph
                continue

            # 중제목: ## → ①
            if stripped.startswith('## '):
                self._subtitle_counter += 1
                subtitle_text = stripped[3:].strip()
                if not any(subtitle_text.startswith(c) for c in self.CIRCLED_NUMBERS):
                    result_lines.append(f"{self._get_circled(self._subtitle_counter)} {subtitle_text}")
                else:
                    result_lines.append(stripped[3:])
                result_lines.append('')  # 빈 줄 추가
                continue

            # 주석: > → ※
            if stripped.startswith('> '):
                note_text = stripped[2:].strip()
                if not note_text.startswith('※'):
                    result_lines.append(f"※ {note_text}")  # ※ 기호 사용
                else:
                    result_lines.append(note_text)
                result_lines.append('')  # 빈 줄 추가
                continue

            # 리스트: - → □ 또는 ㅇ
            if stripped.startswith('- '):
                indent = len(line) - len(line.lstrip())
                content = stripped[2:].strip()

                if indent >= 4:  # 2단계: ㅇ (스페이스는 XML에서 추가)
                    if not content.startswith('ㅇ'):
                        result_lines.append(f"ㅇ {content}")
                    else:
                        result_lines.append(content)
                else:  # 1단계: □
                    if not content.startswith('□'):
                        result_lines.append(f"□ {content}")
                    else:
                        result_lines.append(content)
                result_lines.append('')  # 빈 줄 추가
                continue

            result_lines.append(line)

        return '\n'.join(result_lines)

    def _create_font_faces_xml(self) -> str:
        """글꼴 정의 XML 생성"""
        fonts_xml = []

        # HY헤드라인M
        fonts_xml.append('''
        <hh:fontface lang="HANGUL" fontCnt="1">
            <hh:font id="0" face="HY헤드라인M" type="TTF" isEmbedded="0">
                <hh:typeInfo familyType="FCAT_GOTHIC" weight="8" proportion="0"
                    contrast="0" strokeVariation="1" armStyle="1" letterform="1"
                    midline="1" xHeight="1"/>
            </hh:font>
        </hh:fontface>
        ''')

        # 함초롱바탕
        fonts_xml.append('''
        <hh:fontface lang="HANGUL" fontCnt="1">
            <hh:font id="1" face="함초롱바탕" type="TTF" isEmbedded="0">
                <hh:typeInfo familyType="FCAT_MYEONGJO" weight="4" proportion="0"
                    contrast="0" strokeVariation="1" armStyle="1" letterform="1"
                    midline="1" xHeight="1"/>
            </hh:font>
        </hh:fontface>
        ''')

        # 맑은 고딕
        fonts_xml.append('''
        <hh:fontface lang="HANGUL" fontCnt="1">
            <hh:font id="2" face="맑은 고딕" type="TTF" isEmbedded="0">
                <hh:typeInfo familyType="FCAT_GOTHIC" weight="4" proportion="0"
                    contrast="0" strokeVariation="1" armStyle="1" letterform="1"
                    midline="1" xHeight="1"/>
            </hh:font>
        </hh:fontface>
        ''')

        return '\n'.join(fonts_xml)

    def _apply_fonts_to_section(self, section_xml: str) -> str:
        """섹션 XML에 글꼴 및 들여쓰기 적용 (charPrIDRef 사용, 스페이스로 들여쓰기)"""
        # 네임스페이스 등록
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(section_xml)
        except ET.ParseError:
            return section_xml

        # 3칸 스페이스 (논브레이킹 스페이스)
        INDENT_SPACES = '\u00A0\u00A0\u00A0'

        # 모든 paragraph 찾기
        for para in root.findall('.//hp:p', self.NAMESPACES):
            # 텍스트 내용 확인
            text_content = ''
            first_t_element = None
            for run in para.findall('.//hp:run', self.NAMESPACES):
                for t in run.findall('.//hp:t', self.NAMESPACES):
                    if t.text:
                        text_content += t.text
                        if first_t_element is None:
                            first_t_element = t

            # 레벨 판별
            level = self._determine_level(text_content)
            char_pr_id = self._char_pr_id_map.get(level, '0')

            # ㅇ, ※ 는 첫 번째 텍스트 앞에 스페이스 추가
            if level in ['level2', 'note'] and first_t_element is not None:
                if first_t_element.text and not first_t_element.text.startswith('\u00A0'):
                    first_t_element.text = INDENT_SPACES + first_t_element.text

            # 모든 run의 charPrIDRef 수정
            for run in para.findall('.//hp:run', self.NAMESPACES):
                run.set('charPrIDRef', char_pr_id)

        return ET.tostring(root, encoding='unicode')

    def _determine_level(self, text: str) -> str:
        """텍스트 내용에 따른 레벨 결정"""
        text = text.strip()

        # 대제목 (Ⅰ. Ⅱ. 등)
        if any(text.startswith(r + '.') for r in self.ROMAN_NUMERALS):
            return 'title'

        # 중제목 (① ② 등)
        if any(text.startswith(c) for c in self.CIRCLED_NUMBERS):
            return 'subtitle'

        # 1단계 (□)
        if text.startswith('□'):
            return 'level1'

        # 2단계 (ㅇ)
        if text.startswith('ㅇ') or text.lstrip().startswith('ㅇ'):
            return 'level2'

        # 주석 (※)
        if text.startswith('※') or text.lstrip().startswith('※'):
            return 'note'

        # 기본값
        return 'level1'

    def _apply_margins(self, section_xml: str) -> str:
        """섹션 XML에 A4 여백 적용 (20mm 상하좌우)"""
        # HWPUNIT: 1mm ≈ 283.46 units (7200 units per inch, 1 inch = 25.4mm)
        MARGIN_20MM = 5669  # 20 * 283.46 ≈ 5669

        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(section_xml)
        except ET.ParseError:
            return section_xml

        # hp:pagePr 안의 hp:margin 찾기
        for page_pr in root.findall('.//hp:pagePr', self.NAMESPACES):
            margin = page_pr.find('hp:margin', self.NAMESPACES)
            if margin is None:
                margin = ET.SubElement(page_pr, '{http://www.hancom.co.kr/hwpml/2011/paragraph}margin')

            # 여백 설정 (20mm 상하좌우)
            margin.set('left', str(MARGIN_20MM))
            margin.set('right', str(MARGIN_20MM))
            margin.set('top', str(MARGIN_20MM))
            margin.set('bottom', str(MARGIN_20MM))
            margin.set('header', '0')
            margin.set('footer', '0')
            margin.set('gutter', '0')

        return ET.tostring(root, encoding='unicode')

    def _determine_font_style(self, text: str) -> Tuple[str, int, bool]:
        """텍스트 내용에 따른 글꼴 스타일 결정"""
        text = text.strip()

        # 대제목 (Ⅰ. Ⅱ. 등)
        if any(text.startswith(r + '.') for r in self.ROMAN_NUMERALS):
            return (FontConfig.FONTS['headline'], 18, True)

        # 중제목 (① ② 등)
        if any(text.startswith(c) for c in self.CIRCLED_NUMBERS):
            return (FontConfig.FONTS['hamchorong'], 15, True)

        # 1단계 (□)
        if text.startswith('□'):
            return (FontConfig.FONTS['hamchorong'], 15, False)

        # 2단계 (ㅇ)
        if text.startswith('ㅇ'):
            return (FontConfig.FONTS['hamchorong'], 14, False)

        # 주석 (*)
        if text.startswith('*'):
            return (FontConfig.FONTS['malgun'], 10, False)

        # 기본값
        return (FontConfig.FONTS['hamchorong'], 12, False)

    def convert(self, input_path: str, output_path: str, preprocess: bool = True) -> str:
        """마크다운을 HWPX로 변환"""

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

        if not self.template_path or not os.path.exists(self.template_path):
            raise FileNotFoundError("템플릿 파일을 찾을 수 없습니다")

        # 마크다운 읽기
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        # 전처리
        if preprocess:
            markdown_text = self.preprocess_markdown(markdown_text)
            print("[Preprocessing completed]")

        # 임시 파일에 저장
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
            tmp.write(markdown_text)
            tmp_path = tmp.name

        try:
            # pypandoc-hwpx로 기본 변환
            from pypandoc_hwpx.PandocToHwpx import PandocToHwpx

            # 임시 출력 파일
            temp_output = output_path + '.tmp'
            PandocToHwpx.convert_to_hwpx(tmp_path, temp_output, self.template_path)

            # 글꼴 후처리 적용
            self._postprocess_fonts(temp_output, output_path)

            # 임시 파일 삭제
            if os.path.exists(temp_output):
                os.unlink(temp_output)

            print(f"[OK] Conversion completed: {output_path}")
            return output_path

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _postprocess_fonts(self, input_hwpx: str, output_hwpx: str):
        """HWPX 파일에 글꼴 후처리 및 여백 적용"""

        # 먼저 header.xml을 읽어서 charPr ID와 font ID 매핑 생성
        self._font_id_map = {}  # font name -> font ID
        self._char_pr_id_map = {}  # level -> charPr ID
        self._para_pr_id_map = {}  # indent level -> paraPr ID

        with zipfile.ZipFile(input_hwpx, 'r') as zin:
            header_xml = zin.read('Contents/header.xml').decode('utf-8')
            self._parse_header_fonts(header_xml)

        with zipfile.ZipFile(input_hwpx, 'r') as zin:
            with zipfile.ZipFile(output_hwpx, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    content = zin.read(item.filename)

                    if item.filename == 'Contents/section0.xml':
                        # 섹션 XML에 글꼴 및 여백 적용
                        section_xml = content.decode('utf-8')
                        modified_xml = self._apply_fonts_to_section(section_xml)
                        modified_xml = self._apply_margins(modified_xml)
                        zout.writestr(item, modified_xml.encode('utf-8'))

                    elif item.filename == 'Contents/header.xml':
                        # 헤더에 글꼴 및 charPr 정보 추가
                        header_xml = content.decode('utf-8')
                        modified_header = self._add_fonts_and_styles_to_header(header_xml)
                        zout.writestr(item, modified_header.encode('utf-8'))

                    else:
                        zout.writestr(item, content)

    def _parse_header_fonts(self, header_xml: str) -> None:
        """헤더에서 폰트 ID 파싱"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return

        # fontfaces에서 폰트 ID 찾기
        for fontface in root.findall('.//hh:fontface', self.NAMESPACES):
            if fontface.get('lang') == 'HANGUL':
                for font in fontface.findall('hh:font', self.NAMESPACES):
                    font_id = font.get('id', '0')
                    font_name = font.get('face', '')
                    self._font_id_map[font_name] = font_id

        # charProperties에서 마지막 ID 찾기
        char_props = root.find('.//hh:charProperties', self.NAMESPACES)
        if char_props is not None:
            self._max_char_pr_id = int(char_props.get('itemCnt', '10'))
        else:
            self._max_char_pr_id = 10

    def _add_fonts_and_styles_to_header(self, header_xml: str) -> str:
        """헤더에 폰트 및 charPr 스타일 추가"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return header_xml

        # 1. fontfaces에 필요한 폰트 추가
        fonts_to_add = [
            ('HY헤드라인M', 'FCAT_GOTHIC', '8'),
            ('함초롱바탕', 'FCAT_MYEONGJO', '4'),
            ('맑은 고딕', 'FCAT_GOTHIC', '4'),
        ]

        for fontface in root.findall('.//hh:fontface', self.NAMESPACES):
            if fontface.get('lang') == 'HANGUL':
                existing_fonts = {f.get('face') for f in fontface.findall('hh:font', self.NAMESPACES)}
                font_cnt = int(fontface.get('fontCnt', '0'))

                for font_name, family_type, weight in fonts_to_add:
                    if font_name not in existing_fonts:
                        new_font = ET.SubElement(fontface, '{http://www.hancom.co.kr/hwpml/2011/head}font')
                        new_font.set('id', str(font_cnt))
                        new_font.set('face', font_name)
                        new_font.set('type', 'TTF')
                        new_font.set('isEmbedded', '0')

                        type_info = ET.SubElement(new_font, '{http://www.hancom.co.kr/hwpml/2011/head}typeInfo')
                        type_info.set('familyType', family_type)
                        type_info.set('weight', weight)

                        self._font_id_map[font_name] = str(font_cnt)
                        font_cnt += 1

                fontface.set('fontCnt', str(font_cnt))
                break

        # 2. charProperties에 레벨별 스타일 추가
        char_props = root.find('.//hh:charProperties', self.NAMESPACES)
        if char_props is not None:
            current_id = self._max_char_pr_id

            # 스타일 정의: (level_name, font_name, height, bold)
            styles = [
                ('title', 'HY헤드라인M', 1800, True),      # 대제목 18pt
                ('subtitle', '함초롱바탕', 1500, True),    # 중제목 15pt bold
                ('level1', '함초롱바탕', 1500, False),     # 1단계 15pt
                ('level2', '함초롱바탕', 1400, False),     # 2단계 14pt
                ('note', '맑은 고딕', 1000, False),        # 주석 10pt
            ]

            for level_name, font_name, height, bold in styles:
                font_id = self._font_id_map.get(font_name, '0')

                char_pr = ET.SubElement(char_props, '{http://www.hancom.co.kr/hwpml/2011/head}charPr')
                char_pr.set('id', str(current_id))
                char_pr.set('height', str(height))
                char_pr.set('textColor', '#000000')
                char_pr.set('shadeColor', 'none')
                char_pr.set('useFontSpace', '0')
                char_pr.set('useKerning', '0')
                char_pr.set('symMark', 'NONE')
                char_pr.set('borderFillIDRef', '2')
                if bold:
                    char_pr.set('bold', '1')

                # fontRef - 폰트 참조
                font_ref = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}fontRef')
                font_ref.set('hangul', font_id)
                font_ref.set('latin', '0')
                font_ref.set('hanja', '0')
                font_ref.set('japanese', '0')
                font_ref.set('other', '0')
                font_ref.set('symbol', '0')
                font_ref.set('user', '0')

                # ratio - 장평 비율
                ratio = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}ratio')
                ratio.set('hangul', '100')
                ratio.set('latin', '100')
                ratio.set('hanja', '100')
                ratio.set('japanese', '100')
                ratio.set('other', '100')
                ratio.set('symbol', '100')
                ratio.set('user', '100')

                # spacing - 자간
                spacing = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}spacing')
                spacing.set('hangul', '0')
                spacing.set('latin', '0')
                spacing.set('hanja', '0')
                spacing.set('japanese', '0')
                spacing.set('other', '0')
                spacing.set('symbol', '0')
                spacing.set('user', '0')

                # relSz - 상대 크기
                rel_sz = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}relSz')
                rel_sz.set('hangul', '100')
                rel_sz.set('latin', '100')
                rel_sz.set('hanja', '100')
                rel_sz.set('japanese', '100')
                rel_sz.set('other', '100')
                rel_sz.set('symbol', '100')
                rel_sz.set('user', '100')

                # offset - 위치 오프셋
                offset = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}offset')
                offset.set('hangul', '0')
                offset.set('latin', '0')
                offset.set('hanja', '0')
                offset.set('japanese', '0')
                offset.set('other', '0')
                offset.set('symbol', '0')
                offset.set('user', '0')

                # underline - 밑줄
                underline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}underline')
                underline.set('type', 'NONE')
                underline.set('shape', 'SOLID')
                underline.set('color', '#000000')

                # strikeout - 취소선
                strikeout = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}strikeout')
                strikeout.set('shape', 'NONE')
                strikeout.set('color', '#000000')

                # outline - 외곽선
                outline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}outline')
                outline.set('type', 'NONE')

                # shadow - 그림자
                shadow = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}shadow')
                shadow.set('type', 'NONE')
                shadow.set('color', '#C0C0C0')
                shadow.set('offsetX', '5')
                shadow.set('offsetY', '5')

                self._char_pr_id_map[level_name] = str(current_id)
                current_id += 1

            char_props.set('itemCnt', str(current_id))

        # 3. paraProperties에 레벨별 들여쓰기 스타일 추가
        para_props = root.find('.//hh:paraProperties', self.NAMESPACES)
        if para_props is not None:
            para_cnt = int(para_props.get('itemCnt', '10'))

            # 들여쓰기 설정: (level_name, left_margin in HWPUNIT)
            # 3칸 스페이스 ≈ 850 HWPUNIT (약 3mm)
            para_styles = [
                ('indent0', 0),      # 들여쓰기 없음 (□, Ⅰ., ①)
                ('indent1', 850),    # 3칸 들여쓰기 (ㅇ)
                ('indent2', 850),    # 주석용 (※)
            ]

            for level_name, left_margin in para_styles:
                para_pr = ET.SubElement(para_props, '{http://www.hancom.co.kr/hwpml/2011/head}paraPr')
                para_pr.set('id', str(para_cnt))
                para_pr.set('tabPrIDRef', '1')
                para_pr.set('condense', '0')
                para_pr.set('fontLineHeight', '0')
                para_pr.set('snapToGrid', '1')
                para_pr.set('suppressLineNumbers', '0')
                para_pr.set('checked', '0')

                align = ET.SubElement(para_pr, '{http://www.hancom.co.kr/hwpml/2011/head}align')
                align.set('horizontal', 'LEFT')
                align.set('vertical', 'BASELINE')

                heading = ET.SubElement(para_pr, '{http://www.hancom.co.kr/hwpml/2011/head}heading')
                heading.set('type', 'NONE')
                heading.set('idRef', '0')
                heading.set('level', '0')

                margin = ET.SubElement(para_pr, '{http://www.hancom.co.kr/hwpml/2011/head}margin')
                margin.set('intent', '0')
                margin.set('left', str(left_margin))
                margin.set('right', '0')
                margin.set('prev', '0')
                margin.set('next', '0')

                line_spacing = ET.SubElement(para_pr, '{http://www.hancom.co.kr/hwpml/2011/head}lineSpacing')
                line_spacing.set('type', 'PERCENT')
                line_spacing.set('value', '160')

                border = ET.SubElement(para_pr, '{http://www.hancom.co.kr/hwpml/2011/head}border')
                border.set('borderFillIDRef', '2')
                border.set('offsetLeft', '0')
                border.set('offsetRight', '0')
                border.set('offsetTop', '0')
                border.set('offsetBottom', '0')
                border.set('connect', '0')
                border.set('ignoreMargin', '0')

                self._para_pr_id_map[level_name] = str(para_cnt)
                para_cnt += 1

            para_props.set('itemCnt', str(para_cnt))

        return ET.tostring(root, encoding='unicode')

    def _add_fonts_to_header(self, header_xml: str) -> str:
        """헤더 XML에 글꼴 정의 추가"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        try:
            root = ET.fromstring(header_xml)
        except ET.ParseError:
            return header_xml

        # fontfaces 섹션 찾기
        fontfaces = root.find('.//hh:fontfaces', self.NAMESPACES)
        if fontfaces is None:
            return header_xml

        # 기존 글꼴 목록 확인 및 추가
        existing_fonts = set()
        for fontface in fontfaces.findall('.//hh:font', self.NAMESPACES):
            face = fontface.get('face', '')
            existing_fonts.add(face)

        # 필요한 글꼴 추가
        fonts_to_add = [
            ('HY헤드라인M', 'FCAT_GOTHIC', '8'),
            ('함초롱바탕', 'FCAT_MYEONGJO', '4'),
            ('맑은 고딕', 'FCAT_GOTHIC', '4'),
        ]

        for font_name, family_type, weight in fonts_to_add:
            if font_name not in existing_fonts:
                # 새 fontface 추가
                for ff in fontfaces.findall('hh:fontface', self.NAMESPACES):
                    if ff.get('lang') == 'HANGUL':
                        font_cnt = int(ff.get('fontCnt', '0'))
                        new_font = ET.SubElement(ff, '{http://www.hancom.co.kr/hwpml/2011/head}font')
                        new_font.set('id', str(font_cnt))
                        new_font.set('face', font_name)
                        new_font.set('type', 'TTF')
                        new_font.set('isEmbedded', '0')

                        type_info = ET.SubElement(new_font, '{http://www.hancom.co.kr/hwpml/2011/head}typeInfo')
                        type_info.set('familyType', family_type)
                        type_info.set('weight', weight)

                        ff.set('fontCnt', str(font_cnt + 1))
                        break

        return ET.tostring(root, encoding='unicode')


def convert_with_fonts(input_path: str, output_path: str, template_path: Optional[str] = None) -> str:
    """글꼴 설정이 포함된 변환 함수"""
    converter = OfficialFontConverter(template_path=template_path)
    return converter.convert(input_path, output_path)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python font_converter.py input.md output.hwpx [template.hwpx]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    template_file = sys.argv[3] if len(sys.argv) > 3 else None

    convert_with_fonts(input_file, output_file, template_file)
