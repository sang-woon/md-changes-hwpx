"""
명령행 인터페이스 (CLI)

마크다운 → HWPX 변환을 명령행에서 실행합니다.

사용법:
    hwpx-convert input.md -o output.hwpx
    hwpx-convert input.md -o output.hwpx --template custom.hwpx
    hwpx-convert --guide
"""

import sys
import argparse
from pathlib import Path

from .converter import HwpxConverter, MARKDOWN_GUIDE
from .errors import HwpxConverterError


def main():
    """CLI 메인 진입점"""
    parser = argparse.ArgumentParser(
        prog="hwpx-convert",
        description="마크다운을 공공기관 보고서 스타일 HWPX로 변환합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=MARKDOWN_GUIDE,
    )

    parser.add_argument("input", nargs="?", help="입력 마크다운 파일")
    parser.add_argument("-o", "--output", help="출력 HWPX 파일")
    parser.add_argument("--template", help="참조 HWPX 템플릿")
    parser.add_argument("--no-preprocess", action="store_true", help="전처리 비활성화")
    parser.add_argument("--guide", action="store_true", help="마크다운 작성 가이드 출력")
    parser.add_argument("--version", action="store_true", help="버전 정보 출력")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 출력")

    args = parser.parse_args()

    # 버전 정보
    if args.version:
        from . import __version__

        print(f"hwpx-converter {__version__}")
        sys.exit(0)

    # 가이드 출력
    if args.guide or args.input is None:
        print(MARKDOWN_GUIDE)
        if args.input is None:
            sys.exit(0)

    # 입력 파일 확인
    if args.input is None:
        parser.print_help()
        sys.exit(1)

    # 출력 파일 결정
    input_path = Path(args.input)
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_suffix(".hwpx"))

    # 변환 실행
    try:
        if args.verbose:
            print(f"입력: {args.input}")
            print(f"출력: {output_path}")
            if args.template:
                print(f"템플릿: {args.template}")
            print(f"전처리: {'비활성' if args.no_preprocess else '활성'}")
            print()

        converter = HwpxConverter(template_path=args.template)
        result_path, processing_time, output_size = converter.convert(
            args.input, output_path, preprocess=not args.no_preprocess
        )

        print(f"✅ 변환 완료: {result_path}")
        if args.verbose:
            print(f"   처리 시간: {processing_time}ms")
            print(f"   파일 크기: {output_size:,} bytes")

    except HwpxConverterError as e:
        print(f"❌ 오류 [{e.code.value}]: {e.message}", file=sys.stderr)
        if args.verbose and e.detail:
            print(f"   상세: {e.detail}", file=sys.stderr)
        sys.exit(1)

    except FileNotFoundError as e:
        print(f"❌ 파일을 찾을 수 없습니다: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
