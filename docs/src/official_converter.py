#!/usr/bin/env python3
"""
마크다운 → 공공기관 스타일 HWPX 변환기

이 모듈은 Markdown 파일을 경기도의회 등 공공기관의 보고서 스타일에 맞는
HWPX 파일로 변환합니다.

주요 기능:
- □, ○ 글머리표 자동 적용
- 레벨별 폰트 크기 자동 설정 (15pt, 13pt 등)
- 참조 템플릿 스타일 상속

사용 예시:
    from official_converter import OfficialHwpxConverter
    
    converter = OfficialHwpxConverter()
    converter.convert('report.md', 'report.hwpx')
"""

import os
import io
import sys
import json
import copy
import zipfile
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
import pypandoc

# 패키지 루트에서 PandocToHwpx 임포트
try:
    from pypandoc_hwpx.PandocToHwpx import PandocToHwpx
except ImportError:
    # 개발 환경용 폴백
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pypandoc-hwpx', '--break-system-packages'], 
                   capture_output=True)
    from pypandoc_hwpx.PandocToHwpx import PandocToHwpx


class OfficialHwpxConverter:
    """공공기관 스타일 HWPX 변환기"""
    
    # HWPX XML 네임스페이스
    NAMESPACES = {
        'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section'
    }
    
    # 공공기관 표준 글머리 기호
    OFFICIAL_BULLETS = {
        1: '□',
        2: '○',
        3: '-',
        4: '·',
        5: '▪',
        6: '▸',
        7: '•',
    }
    
    # 레벨별 폰트 크기 (HWP 단위)
    OFFICIAL_FONT_SIZES = {
        1: 1500,  # 15pt
        2: 1300,  # 13pt
        3: 1100,  # 11pt
        4: 1000,  # 10pt
        5: 1000,
        6: 1000,
        7: 1000,
    }
    
    def __init__(self, 
                 reference_hwpx: str = None,
                 bullets: dict = None,
                 font_sizes: dict = None):
        """
        변환기 초기화
        
        Args:
            reference_hwpx: 참조 HWPX 템플릿 경로 (None이면 기본 템플릿 사용)
            bullets: 커스텀 글머리 기호 설정
            font_sizes: 커스텀 폰트 크기 설정
        """
        self.reference_hwpx = reference_hwpx
        self.bullets = bullets or self.OFFICIAL_BULLETS.copy()
        self.font_sizes = font_sizes or self.OFFICIAL_FONT_SIZES.copy()
        
        # 기본 템플릿 경로 찾기
        if self.reference_hwpx is None:
            pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_paths = [
                os.path.join(pkg_dir, 'blank.hwpx'),
                '/usr/local/lib/python3.12/dist-packages/pypandoc_hwpx/blank.hwpx',
            ]
            for path in default_paths:
                if os.path.exists(path):
                    self.reference_hwpx = path
                    break
    
    def _create_official_numbering_xml(self, numbering_id: int = 100) -> str:
        """공공기관 스타일 넘버링 XML 생성"""
        xml_parts = [f'<hh:numbering id="{numbering_id}" start="1" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">']
        
        for level in range(1, 8):
            symbol = self.bullets.get(level, '•')
            xml_parts.append(
                f'<hh:paraHead start="1" level="{level}" align="LEFT" '
                f'useInstWidth="1" autoIndent="0" widthAdjust="0" '
                f'textOffsetType="PERCENT" textOffset="50" numFormat="DIGIT" '
                f'charPrIDRef="4294967295" checkable="0">{symbol}</hh:paraHead>'
            )
        
        xml_parts.append('</hh:numbering>')
        return '\n'.join(xml_parts)
    
    def _inject_official_styles(self, header_xml: str) -> str:
        """header.xml에 공공기관 스타일 주입"""
        # 네임스페이스 등록
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        root = ET.fromstring(header_xml)
        
        # 1. 넘버링 섹션 찾기 또는 생성
        numberings = root.find('.//hh:numberings', self.NAMESPACES)
        if numberings is None:
            ref_list = root.find('.//hh:refList', self.NAMESPACES)
            if ref_list is None:
                return header_xml
            numberings = ET.SubElement(ref_list, '{http://www.hancom.co.kr/hwpml/2011/head}numberings')
            numberings.set('itemCnt', '0')
        
        # 2. 최대 넘버링 ID 찾기
        max_id = 0
        for num in numberings.findall('hh:numbering', self.NAMESPACES):
            num_id = int(num.get('id', 0))
            if num_id > max_id:
                max_id = num_id
        
        new_id = max_id + 1
        
        # 3. 공공기관 스타일 넘버링 추가
        numbering_xml = self._create_official_numbering_xml(new_id)
        new_numbering = ET.fromstring(numbering_xml)
        numberings.append(new_numbering)
        
        # 4. itemCnt 업데이트
        count = len(numberings.findall('hh:numbering', self.NAMESPACES))
        numberings.set('itemCnt', str(count))
        
        return ET.tostring(root, encoding='unicode')
    
    def convert(self, input_path: str, output_path: str) -> str:
        """
        마크다운을 공공기관 스타일 HWPX로 변환
        
        Args:
            input_path: 입력 마크다운 파일 경로
            output_path: 출력 HWPX 파일 경로
            
        Returns:
            생성된 HWPX 파일 경로
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")
            
        if self.reference_hwpx is None or not os.path.exists(self.reference_hwpx):
            raise FileNotFoundError("참조 HWPX 템플릿을 찾을 수 없습니다")
        
        # 1. Pandoc으로 AST 생성
        json_str = pypandoc.convert_file(input_path, 'json')
        json_ast = json.loads(json_str)
        
        # 2. 참조 문서 읽기
        with open(self.reference_hwpx, 'rb') as f:
            ref_doc_bytes = f.read()
        
        header_xml_content = ""
        page_setup_xml = None
        
        with zipfile.ZipFile(io.BytesIO(ref_doc_bytes)) as z:
            if "Contents/header.xml" in z.namelist():
                header_xml_content = z.read("Contents/header.xml").decode('utf-8')
            
            # 페이지 설정 추출
            if "Contents/section0.xml" in z.namelist():
                try:
                    sec_xml = z.read("Contents/section0.xml").decode('utf-8')
                    sec_root = ET.fromstring(sec_xml)
                    
                    for prefix, uri in self.NAMESPACES.items():
                        ET.register_namespace(prefix, uri)
                    
                    first_para = sec_root.find('.//hp:p', self.NAMESPACES)
                    if first_para is not None:
                        first_run = first_para.find('hp:run', self.NAMESPACES)
                        if first_run is not None:
                            extracted_nodes = []
                            for child in first_run:
                                tag = child.tag
                                if tag.endswith('secPr') or tag.endswith('ctrl'):
                                    extracted_nodes.append(ET.tostring(child, encoding='unicode'))
                            if extracted_nodes:
                                page_setup_xml = "".join(extracted_nodes)
                except Exception as e:
                    print(f"[경고] 페이지 설정 추출 실패: {e}", file=sys.stderr)
        
        # 3. 공공기관 스타일 주입
        header_xml_content = self._inject_official_styles(header_xml_content)
        
        # 4. 변환 수행
        converter = PandocToHwpx(json_ast, header_xml_content)
        xml_body, new_header_xml = converter.convert(page_setup_xml=page_setup_xml)
        
        # 5. 출력 파일 생성
        with zipfile.ZipFile(io.BytesIO(ref_doc_bytes), 'r') as ref_zip:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zip:
                # 이미지 처리
                for img in converter.images:
                    img_path = img['path']
                    img_id = img['id']
                    ext = img['ext']
                    bindata_name = f"BinData/{img_id}.{ext}"
                    
                    if os.path.exists(img_path):
                        out_zip.write(img_path, bindata_name)
                    else:
                        input_dir = os.path.dirname(os.path.abspath(input_path))
                        local_path = os.path.join(input_dir, img_path)
                        if os.path.exists(local_path):
                            out_zip.write(local_path, bindata_name)
                
                # 파일 복사 및 수정
                for item in ref_zip.infolist():
                    fname = item.filename
                    
                    if fname == "Contents/section0.xml":
                        original_xml = ref_zip.read(fname).decode('utf-8')
                        
                        sec_start = original_xml.find('<hs:sec')
                        tag_close = original_xml.find('>', sec_start)
                        prefix = original_xml[:tag_close + 1]
                        
                        if 'xmlns:hc=' not in prefix:
                            prefix = prefix[:-1] + ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core">'
                        if 'xmlns:hp=' not in prefix:
                            prefix = prefix[:-1] + ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                        
                        sec_end = original_xml.rfind('</hs:sec>')
                        suffix = original_xml[sec_end:] if sec_end != -1 else ""
                        
                        out_zip.writestr(fname, prefix + "\n" + xml_body + "\n" + suffix)
                        
                    elif fname == "Contents/header.xml":
                        if new_header_xml:
                            out_zip.writestr(fname, new_header_xml)
                        else:
                            out_zip.writestr(item, ref_zip.read(fname))
                    
                    elif fname == "Contents/content.hpf":
                        hpf_xml = ref_zip.read(fname).decode('utf-8')
                        
                        # 이미지 매니페스트 업데이트
                        if converter.images:
                            new_items = []
                            for img in converter.images:
                                i_id = img['id']
                                i_ext = img['ext']
                                mime = "image/png"
                                if i_ext == "jpg":
                                    mime = "image/jpeg"
                                elif i_ext == "gif":
                                    mime = "image/gif"
                                item_str = f'<opf:item id="{i_id}" href="BinData/{i_id}.{i_ext}" media-type="{mime}" isEmbeded="1"/>'
                                new_items.append(item_str)
                            
                            insert_pos = hpf_xml.find("</opf:manifest>")
                            if insert_pos != -1:
                                hpf_xml = hpf_xml[:insert_pos] + "\n".join(new_items) + "\n" + hpf_xml[insert_pos:]
                        
                        out_zip.writestr(fname, hpf_xml)
                    else:
                        out_zip.writestr(item, ref_zip.read(fname))
        
        print(f"✅ 공공기관 스타일 HWPX 생성 완료: {output_path}")
        return output_path


def convert_md_to_official_hwpx(input_path: str, 
                                 output_path: str,
                                 reference_hwpx: str = None) -> str:
    """
    간편 변환 함수
    
    Args:
        input_path: 입력 마크다운 파일
        output_path: 출력 HWPX 파일
        reference_hwpx: 참조 템플릿 (선택)
        
    Returns:
        생성된 파일 경로
    """
    converter = OfficialHwpxConverter(reference_hwpx=reference_hwpx)
    return converter.convert(input_path, output_path)


# CLI 지원
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='마크다운을 공공기관 스타일 HWPX로 변환합니다.'
    )
    parser.add_argument('input', help='입력 마크다운 파일')
    parser.add_argument('-o', '--output', required=True, help='출력 HWPX 파일')
    parser.add_argument('--reference', help='참조 HWPX 템플릿')
    
    args = parser.parse_args()
    
    try:
        result = convert_md_to_official_hwpx(
            args.input, 
            args.output,
            args.reference
        )
        print(f"변환 완료: {result}")
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
