#!/usr/bin/env python3
"""
공공기관 보고서 스타일 HWPX 템플릿 생성기

이 모듈은 경기도의회 등 공공기관에서 사용하는 보고서 스타일에 맞는
HWPX 템플릿을 생성합니다.

글머리 기호 계층:
- Level 1: □ (15pt)
- Level 2: ○ (13pt)  
- Level 3: - (11pt)
"""

import os
import io
import copy
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Tuple


class OfficialStyleTemplate:
    """공공기관 보고서 스타일 템플릿 생성기"""
    
    # HWPX XML 네임스페이스
    NAMESPACES = {
        'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section'
    }
    
    # 공공기관 표준 글머리 기호
    BULLET_SYMBOLS = {
        1: '□',  # Level 1: 네모 (15pt)
        2: '○',  # Level 2: 동그라미 (13pt)
        3: '-',  # Level 3: 대시 (11pt)
        4: '·',  # Level 4: 점 (10pt)
        5: '▪',  # Level 5: 작은 네모 (10pt)
        6: '▸',  # Level 6: 화살표 (10pt)
        7: '•',  # Level 7: 원형 (10pt)
    }
    
    # 레벨별 폰트 크기 (HWP 단위: 1pt = 100)
    FONT_SIZES = {
        1: 1500,  # 15pt
        2: 1300,  # 13pt
        3: 1100,  # 11pt
        4: 1000,  # 10pt
        5: 1000,  # 10pt
        6: 1000,  # 10pt
        7: 1000,  # 10pt
    }
    
    # 공공기관 표준 폰트
    DEFAULT_FONTS = {
        'title': 'HY헤드라인M',  # 제목용
        'body': '맑은 고딕',     # 본문용
        'bullet': '맑은 고딕',   # 글머리표용
    }
    
    def __init__(self, base_hwpx_path: str):
        """
        기본 HWPX 템플릿을 기반으로 공공기관 스타일 생성기 초기화
        
        Args:
            base_hwpx_path: 기반이 될 blank.hwpx 파일 경로
        """
        self.base_path = base_hwpx_path
        self.header_xml = None
        self.header_root = None
        self.zip_content = None
        
        self._load_template()
        
    def _load_template(self):
        """기본 템플릿 로드"""
        with open(self.base_path, 'rb') as f:
            self.zip_content = f.read()
            
        with zipfile.ZipFile(io.BytesIO(self.zip_content)) as z:
            self.header_xml = z.read('Contents/header.xml').decode('utf-8')
            
        # 네임스페이스 등록
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)
            
        self.header_root = ET.fromstring(self.header_xml)
        
    def _find_max_id(self, tag_name: str) -> int:
        """특정 태그의 최대 ID 찾기"""
        max_id = 0
        for elem in self.header_root.findall(f'.//{tag_name}', self.NAMESPACES):
            elem_id = int(elem.get('id', 0))
            if elem_id > max_id:
                max_id = elem_id
        return max_id
    
    def _add_custom_fonts(self, fonts: Dict[str, str]) -> None:
        """커스텀 폰트 추가"""
        fontfaces = self.header_root.find('.//hh:fontfaces', self.NAMESPACES)
        if fontfaces is None:
            return
            
        for fontface in fontfaces.findall('hh:fontface', self.NAMESPACES):
            max_font_id = 0
            for font in fontface.findall('hh:font', self.NAMESPACES):
                font_id = int(font.get('id', 0))
                if font_id > max_font_id:
                    max_font_id = font_id
            
            # 새 폰트 추가
            for font_name in fonts.values():
                if font_name not in [f.get('face') for f in fontface.findall('hh:font', self.NAMESPACES)]:
                    new_font = ET.SubElement(fontface, '{http://www.hancom.co.kr/hwpml/2011/head}font')
                    max_font_id += 1
                    new_font.set('id', str(max_font_id))
                    new_font.set('face', font_name)
                    new_font.set('type', 'TTF')
                    new_font.set('isEmbedded', '0')
                    
            # fontCnt 업데이트
            font_count = len(fontface.findall('hh:font', self.NAMESPACES))
            fontface.set('fontCnt', str(font_count))
    
    def _create_bullet_char_pr(self, level: int, font_size: int) -> int:
        """글머리표용 CharPr(글자 속성) 생성"""
        char_props = self.header_root.find('.//hh:charProperties', self.NAMESPACES)
        if char_props is None:
            return 0
            
        max_id = self._find_max_id('hh:charPr')
        new_id = max_id + level
        
        # 새 글자 속성 생성
        char_pr = ET.SubElement(char_props, '{http://www.hancom.co.kr/hwpml/2011/head}charPr')
        char_pr.set('id', str(new_id))
        char_pr.set('height', str(font_size))
        char_pr.set('textColor', '#000000')
        char_pr.set('shadeColor', 'none')
        char_pr.set('useFontSpace', '0')
        char_pr.set('useKerning', '0')
        char_pr.set('symMark', 'NONE')
        char_pr.set('borderFillIDRef', '2')
        
        # 폰트 참조
        font_ref = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}fontRef')
        for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
            font_ref.set(lang, '0')
        
        # 비율
        ratio = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}ratio')
        for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
            ratio.set(lang, '100')
            
        # 간격
        spacing = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}spacing')
        for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
            spacing.set(lang, '0')
            
        # 상대 크기
        rel_sz = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}relSz')
        for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
            rel_sz.set(lang, '100')
            
        # 오프셋
        offset = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}offset')
        for lang in ['hangul', 'latin', 'hanja', 'japanese', 'other', 'symbol', 'user']:
            offset.set(lang, '0')
        
        # 밑줄
        underline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}underline')
        underline.set('type', 'NONE')
        underline.set('shape', 'SOLID')
        underline.set('color', '#000000')
        
        # 취소선
        strikeout = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}strikeout')
        strikeout.set('shape', 'NONE')
        strikeout.set('color', '#000000')
        
        # 외곽선
        outline = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}outline')
        outline.set('type', 'NONE')
        
        # 그림자
        shadow = ET.SubElement(char_pr, '{http://www.hancom.co.kr/hwpml/2011/head}shadow')
        shadow.set('type', 'NONE')
        shadow.set('color', '#C0C0C0')
        shadow.set('offsetX', '5')
        shadow.set('offsetY', '5')
        
        return new_id
    
    def _create_official_numbering(self) -> int:
        """공공기관 스타일 글머리표 정의 생성"""
        numberings = self.header_root.find('.//hh:numberings', self.NAMESPACES)
        if numberings is None:
            ref_list = self.header_root.find('.//hh:refList', self.NAMESPACES)
            if ref_list is None:
                return 0
            numberings = ET.SubElement(ref_list, '{http://www.hancom.co.kr/hwpml/2011/head}numberings')
            numberings.set('itemCnt', '0')
        
        max_id = 0
        for num in numberings.findall('hh:numbering', self.NAMESPACES):
            num_id = int(num.get('id', 0))
            if num_id > max_id:
                max_id = num_id
        
        new_id = max_id + 1
        
        # 새 넘버링 요소 생성
        numbering = ET.SubElement(numberings, '{http://www.hancom.co.kr/hwpml/2011/head}numbering')
        numbering.set('id', str(new_id))
        numbering.set('start', '1')
        
        # 각 레벨별 글머리표 정의
        for level in range(1, 8):
            symbol = self.BULLET_SYMBOLS.get(level, '•')
            font_size = self.FONT_SIZES.get(level, 1000)
            
            # 해당 레벨용 글자 속성 생성
            char_pr_id = self._create_bullet_char_pr(level, font_size)
            
            para_head = ET.SubElement(numbering, '{http://www.hancom.co.kr/hwpml/2011/head}paraHead')
            para_head.set('start', '1')
            para_head.set('level', str(level))
            para_head.set('align', 'LEFT')
            para_head.set('useInstWidth', '1')
            para_head.set('autoIndent', '0')
            para_head.set('widthAdjust', '0')
            para_head.set('textOffsetType', 'PERCENT')
            para_head.set('textOffset', '50')
            para_head.set('numFormat', 'DIGIT')
            para_head.set('charPrIDRef', str(char_pr_id))
            para_head.set('checkable', '0')
            para_head.text = symbol
        
        return new_id
    
    def _update_item_counts(self):
        """각 속성 그룹의 itemCnt 업데이트"""
        for prop_name in ['charProperties', 'paraProperties', 'numberings', 'borderFills']:
            props = self.header_root.find(f'.//hh:{prop_name}', self.NAMESPACES)
            if props is not None:
                child_tag = prop_name[:-3] if prop_name.endswith('ies') else prop_name[:-1]
                # charProperties -> charPr, paraProperties -> paraPr
                if prop_name == 'charProperties':
                    child_tag = 'charPr'
                elif prop_name == 'paraProperties':
                    child_tag = 'paraPr'
                elif prop_name == 'numberings':
                    child_tag = 'numbering'
                elif prop_name == 'borderFills':
                    child_tag = 'borderFill'
                    
                count = len(props.findall(f'hh:{child_tag}', self.NAMESPACES))
                props.set('itemCnt', str(count))
    
    def generate(self, output_path: str, 
                 custom_bullets: Optional[Dict[int, str]] = None,
                 custom_sizes: Optional[Dict[int, int]] = None,
                 custom_fonts: Optional[Dict[str, str]] = None) -> str:
        """
        공공기관 스타일 템플릿 생성
        
        Args:
            output_path: 출력 HWPX 파일 경로
            custom_bullets: 커스텀 글머리 기호 (레벨: 기호)
            custom_sizes: 커스텀 폰트 크기 (레벨: 크기)
            custom_fonts: 커스텀 폰트 (용도: 폰트명)
            
        Returns:
            생성된 템플릿 파일 경로
        """
        # 커스텀 설정 적용
        if custom_bullets:
            self.BULLET_SYMBOLS.update(custom_bullets)
        if custom_sizes:
            self.FONT_SIZES.update(custom_sizes)
        if custom_fonts:
            self._add_custom_fonts(custom_fonts)
        
        # 공공기관 스타일 넘버링 생성
        self._create_official_numbering()
        
        # 아이템 카운트 업데이트
        self._update_item_counts()
        
        # 수정된 header.xml
        new_header_xml = ET.tostring(self.header_root, encoding='unicode')
        
        # 새 HWPX 파일 생성
        with zipfile.ZipFile(io.BytesIO(self.zip_content), 'r') as ref_zip:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zip:
                for item in ref_zip.infolist():
                    if item.filename == 'Contents/header.xml':
                        out_zip.writestr(item.filename, new_header_xml)
                    else:
                        out_zip.writestr(item, ref_zip.read(item.filename))
        
        return output_path


def create_official_template(base_hwpx: str, output_path: str) -> str:
    """
    경기도의회 등 공공기관용 표준 템플릿 생성
    
    기본 스타일:
    - Level 1: □ (15pt)
    - Level 2: ○ (13pt)
    - Level 3: - (11pt)
    """
    generator = OfficialStyleTemplate(base_hwpx)
    return generator.generate(
        output_path,
        custom_bullets={
            1: '□',
            2: '○',
            3: '-',
            4: '·',
        },
        custom_sizes={
            1: 1500,  # 15pt
            2: 1300,  # 13pt
            3: 1100,  # 11pt
            4: 1000,  # 10pt
        }
    )


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("사용법: python official_template_generator.py <base.hwpx> <output.hwpx>")
        sys.exit(1)
    
    base_path = sys.argv[1]
    output_path = sys.argv[2]
    
    result = create_official_template(base_path, output_path)
    print(f"✅ 공공기관 스타일 템플릿 생성 완료: {result}")
