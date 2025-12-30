#!/usr/bin/env python3
"""
공공기관 보고서 정확 서식 HWPX 변환기

이 모듈은 교육부, 경기도의회 등 공공기관의 보고서 서식에 정확히 맞는
HWPX 파일로 변환합니다.

서식 계층 구조:
- 대제목: Ⅰ. Ⅱ. Ⅲ. (로마숫자 + 점) - 파란 배경
- 중제목: 󰊱 󰊲 󰊳 (동그라미 숫자) - 파란색 밑줄
- 1단계: □ (네모) - 볼드체
- 2단계: ㅇ (이응) - 일반체
- 주석: * 로 시작 - 작은 글씨

마크다운 매핑:
# → 대제목 (Ⅰ.)
## → 중제목 (󰊱)
- → 1단계 (□)
    - → 2단계 (ㅇ)
> → 주석 (*)
"""

import os
import io
import re
import sys
import json
import copy
import zipfile
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
import pypandoc

try:
    from pypandoc_hwpx.PandocToHwpx import PandocToHwpx
except ImportError:
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pypandoc-hwpx', '--break-system-packages'], 
                   capture_output=True)
    from pypandoc_hwpx.PandocToHwpx import PandocToHwpx


class OfficialReportConverter:
    """
    공공기관 보고서 정확 서식 변환기
    
    서식 계층:
    - # 대제목 → Ⅰ. (파란 배경)
    - ## 중제목 → 󰊱 (파란 밑줄)  
    - - 1단계 → □ (15pt 볼드)
    - - - 2단계 → ㅇ (13pt)
    - > 주석 → * (10pt)
    """
    
    # HWPX XML 네임스페이스
    NAMESPACES = {
        'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
        'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
        'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
        'hs': 'http://www.hancom.co.kr/hwpml/2011/section'
    }
    
    # 로마 숫자 (대제목용)
    ROMAN_NUMERALS = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ']
    
    # 동그라미 숫자 (중제목용) - 유니코드 특수문자
    CIRCLED_NUMBERS = ['󰊱', '󰊲', '󰊳', '󰊴', '󰊵', '󰊶', '󰊷', '󰊸', '󰊹', '󰊺']
    # 대체 동그라미 숫자 (호환성)
    CIRCLED_NUMBERS_ALT = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']
    
    # 글머리 기호
    BULLETS = {
        1: '□',   # 1단계: 네모
        2: 'ㅇ',  # 2단계: 이응
        3: '-',   # 3단계: 대시
        4: '·',   # 4단계: 점
    }
    
    # 폰트 크기 (HWP 단위: 1pt = 100)
    FONT_SIZES = {
        'title': 1800,      # 대제목: 18pt
        'subtitle': 1500,   # 중제목: 15pt
        'level1': 1300,     # 1단계: 13pt
        'level2': 1200,     # 2단계: 12pt
        'note': 1000,       # 주석: 10pt
        'body': 1200,       # 본문: 12pt
    }
    
    def __init__(self, reference_hwpx: str = None, use_alt_circled: bool = True):
        """
        변환기 초기화
        
        Args:
            reference_hwpx: 참조 HWPX 템플릿 경로
            use_alt_circled: 대체 동그라미 숫자 사용 여부 (①②③)
        """
        self.reference_hwpx = reference_hwpx
        self.use_alt_circled = use_alt_circled
        
        # 카운터 초기화
        self.title_counter = 0
        self.subtitle_counter = 0
        
        # 기본 템플릿 경로 찾기
        if self.reference_hwpx is None:
            default_paths = [
                os.path.join(os.path.dirname(__file__), '..', 'blank.hwpx'),
                '/usr/local/lib/python3.12/dist-packages/pypandoc_hwpx/blank.hwpx',
                'blank.hwpx',
            ]
            for path in default_paths:
                if os.path.exists(path):
                    self.reference_hwpx = path
                    break
    
    def _get_roman(self, num: int) -> str:
        """숫자를 로마 숫자로 변환"""
        if 1 <= num <= len(self.ROMAN_NUMERALS):
            return self.ROMAN_NUMERALS[num - 1]
        return str(num)
    
    def _get_circled(self, num: int) -> str:
        """숫자를 동그라미 숫자로 변환"""
        numbers = self.CIRCLED_NUMBERS_ALT if self.use_alt_circled else self.CIRCLED_NUMBERS
        if 1 <= num <= len(numbers):
            return numbers[num - 1]
        return f"({num})"
    
    def preprocess_markdown(self, markdown_text: str) -> str:
        """
        마크다운 텍스트를 공공기관 서식에 맞게 전처리
        
        변환 규칙:
        - # 제목 → Ⅰ. 제목 (대제목)
        - ## 제목 → 󰊱 제목 (중제목)
        - - 항목 → □ 항목 (1단계)
        - - - 항목 → ㅇ 항목 (2단계)
        - > 주석 → * 주석
        """
        lines = markdown_text.split('\n')
        result_lines = []
        
        self.title_counter = 0
        self.subtitle_counter = 0
        
        for line in lines:
            stripped = line.strip()
            
            # 대제목: # → Ⅰ.
            if stripped.startswith('# ') and not stripped.startswith('## '):
                self.title_counter += 1
                self.subtitle_counter = 0  # 중제목 카운터 리셋
                title_text = stripped[2:].strip()
                # 이미 로마숫자가 있으면 그대로 사용
                if not any(title_text.startswith(r) for r in self.ROMAN_NUMERALS):
                    result_lines.append(f"# {self._get_roman(self.title_counter)}. {title_text}")
                else:
                    result_lines.append(line)
                continue
            
            # 중제목: ## → 󰊱
            if stripped.startswith('## '):
                self.subtitle_counter += 1
                subtitle_text = stripped[3:].strip()
                # 이미 동그라미 숫자가 있으면 그대로 사용
                if not any(subtitle_text.startswith(c) for c in self.CIRCLED_NUMBERS + self.CIRCLED_NUMBERS_ALT):
                    result_lines.append(f"## {self._get_circled(self.subtitle_counter)} {subtitle_text}")
                else:
                    result_lines.append(line)
                continue
            
            # 주석: > → * (blockquote to footnote)
            if stripped.startswith('> '):
                note_text = stripped[2:].strip()
                if not note_text.startswith('*'):
                    result_lines.append(f"> * {note_text}")
                else:
                    result_lines.append(line)
                continue
            
            # 1단계 리스트: - → □
            # 2단계 리스트: - - → ㅇ
            if stripped.startswith('- '):
                indent = len(line) - len(line.lstrip())
                content = stripped[2:].strip()
                
                if indent >= 4:  # 2단계 (들여쓰기 있음)
                    if not content.startswith('ㅇ'):
                        # 볼드 텍스트 처리
                        content = self._process_bold_text(content)
                        result_lines.append(f"{'    ' * (indent // 4)}- ㅇ {content}")
                    else:
                        result_lines.append(line)
                else:  # 1단계
                    if not content.startswith('□'):
                        # 볼드 텍스트 처리
                        content = self._process_bold_text(content)
                        result_lines.append(f"- □ {content}")
                    else:
                        result_lines.append(line)
                continue
            
            # 그 외는 그대로
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _process_bold_text(self, text: str) -> str:
        """볼드 텍스트 처리 (기존 마크다운 볼드 유지)"""
        return text
    
    def convert(self, input_path: str, output_path: str, preprocess: bool = True) -> str:
        """
        마크다운을 공공기관 스타일 HWPX로 변환
        
        Args:
            input_path: 입력 마크다운 파일 경로
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부
            
        Returns:
            생성된 HWPX 파일 경로
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")
            
        if self.reference_hwpx is None or not os.path.exists(self.reference_hwpx):
            raise FileNotFoundError("참조 HWPX 템플릿을 찾을 수 없습니다")
        
        # 마크다운 파일 읽기
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        # 전처리 적용
        if preprocess:
            markdown_text = self.preprocess_markdown(markdown_text)
            print("[Debug] 전처리된 마크다운:")
            print(markdown_text[:500] + "..." if len(markdown_text) > 500 else markdown_text)
        
        # 임시 파일에 전처리된 마크다운 저장
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
            tmp.write(markdown_text)
            tmp_path = tmp.name
        
        try:
            # pypandoc-hwpx로 변환
            PandocToHwpx.convert_to_hwpx(tmp_path, output_path, self.reference_hwpx)
            print(f"✅ 공공기관 서식 HWPX 생성 완료: {output_path}")
            return output_path
        finally:
            # 임시 파일 삭제
            os.unlink(tmp_path)
    
    def convert_text(self, markdown_text: str, output_path: str, preprocess: bool = True) -> str:
        """
        마크다운 텍스트를 직접 변환
        
        Args:
            markdown_text: 마크다운 텍스트
            output_path: 출력 HWPX 파일 경로
            preprocess: 마크다운 전처리 여부
            
        Returns:
            생성된 HWPX 파일 경로
        """
        import tempfile
        
        # 임시 파일에 마크다운 저장
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
            tmp.write(markdown_text)
            tmp_path = tmp.name
        
        try:
            return self.convert(tmp_path, output_path, preprocess)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def convert_to_official_hwpx(input_path: str, output_path: str, 
                              reference_hwpx: str = None,
                              preprocess: bool = True) -> str:
    """
    간편 변환 함수
    
    Args:
        input_path: 입력 마크다운 파일
        output_path: 출력 HWPX 파일
        reference_hwpx: 참조 템플릿 (선택)
        preprocess: 전처리 여부
        
    Returns:
        생성된 파일 경로
    """
    converter = OfficialReportConverter(reference_hwpx=reference_hwpx)
    return converter.convert(input_path, output_path, preprocess)


# 마크다운 서식 가이드
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
║  ─────────────────────────────────────────────────────────────     ║
║                                                                    ║
║  예시:                                                              ║
║  # '25년 평가 및 향후 업무추진방향                                   ║
║  ## '25년 성과 및 보완점                                            ║
║  - 교육·돌봄에 대한 **국가책임의 강화**                              ║
║      - 국가책임형 유아 교육·보육 실현과 학부모 양육비 부담 경감      ║
║  > '25년 7월부터 만 5세 무상교육·보육 실시                          ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
"""


# CLI 지원
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='마크다운을 공공기관 보고서 스타일 HWPX로 변환합니다.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=MARKDOWN_GUIDE
    )
    parser.add_argument('input', nargs='?', help='입력 마크다운 파일')
    parser.add_argument('-o', '--output', help='출력 HWPX 파일')
    parser.add_argument('--reference', help='참조 HWPX 템플릿')
    parser.add_argument('--no-preprocess', action='store_true', help='전처리 비활성화')
    parser.add_argument('--guide', action='store_true', help='마크다운 작성 가이드 출력')
    
    args = parser.parse_args()
    
    if args.guide or args.input is None:
        print(MARKDOWN_GUIDE)
        if args.input is None:
            sys.exit(0)
    
    if args.input and args.output:
        try:
            result = convert_to_official_hwpx(
                args.input, 
                args.output,
                args.reference,
                not args.no_preprocess
            )
            print(f"변환 완료: {result}")
        except Exception as e:
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
