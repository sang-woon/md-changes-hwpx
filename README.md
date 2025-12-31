# HWPX Converter

마크다운(Markdown) 문서를 공공기관 보고서 스타일의 HWPX(한글 문서) 파일로 변환하는 Python 라이브러리입니다.

## 주요 기능

- **공공기관 표준 서식**: Ⅰ.→①→□→ㅇ 형태의 계층 구조 자동 적용
- **레벨별 폰트 크기**: 대제목(18pt), 중제목(15pt), 1단계(13pt), 2단계(12pt)
- **웹 UI 편집기**: Markdown 실시간 미리보기 및 HWPX 변환
- **ChatGPT 프롬프트**: AI가 Markdown으로만 응답하도록 하는 프롬프트 제공
- **REST API 서비스**: FastAPI 기반 웹 서비스
- **파일 자동 삭제**: 24시간 후 자동 정리 (보안)

## 설치

### 필수 요구사항

```bash
# Pandoc 설치 (필수)
sudo apt-get install pandoc  # Ubuntu/Debian
brew install pandoc          # macOS
choco install pandoc         # Windows

# Python 패키지 설치
pip install -e .
```

## 사용 방법

### 1. 웹 UI (권장)

```bash
# 서버 시작
hwpx-server

# 웹 브라우저에서 접속
# http://localhost:8000
```

**워크플로우:**
1. 주제 입력 → **ChatGPT 프롬프트** 생성 및 복사
2. ChatGPT에서 문서 생성 → 결과를 **편집기에 붙여넣기**
3. 미리보기 확인 → **HWPX 변환** 버튼 클릭

### 2. Python 코드

```python
from hwpx_converter import HwpxConverter

# 변환기 초기화
converter = HwpxConverter()

# 마크다운 → HWPX 변환
converter.convert('report.md', 'report.hwpx')
```

### 3. 명령행 도구

```bash
# 기본 변환
hwpx-convert report.md -o report.hwpx

# 참조 템플릿 지정
hwpx-convert report.md -o report.hwpx --template custom.hwpx

# 마크다운 작성 가이드 확인
hwpx-convert --guide
```

### 4. REST API

```bash
# API 문서: http://localhost:8000/docs
```

## 마크다운 서식 매핑

| 마크다운 입력 | HWPX 출력 | 설명 |
|-------------|-----------|------|
| `# 제목` | Ⅰ. 제목 | 대제목 (로마숫자) |
| `## 제목` | ① 제목 | 중제목 (동그라미숫자) |
| `- 항목` | □ 항목 | 1단계 (13pt) |
| `    - 항목` | ㅇ 항목 | 2단계 (12pt) |
| `> 주석` | * 주석 | 주석 (10pt) |

### 예시

**입력 (Markdown)**
```markdown
# '25년 평가 및 향후 업무추진방향

## '25년 성과 및 보완점

- 교육·돌봄에 대한 **국가책임의 강화**
    - 국가책임형 유아 교육·보육 실현

> '25년 7월부터 만 5세 무상교육·보육 실시
```

**출력 (HWPX)**
```
Ⅰ. '25년 평가 및 향후 업무추진방향

① '25년 성과 및 보완점

□ 교육·돌봄에 대한 국가책임의 강화
  ㅇ 국가책임형 유아 교육·보육 실현

* '25년 7월부터 만 5세 무상교육·보육 실시
```

## ChatGPT 프롬프트 사용법

웹 UI에서 **ChatGPT 프롬프트** 버튼을 클릭하거나, API를 통해 프롬프트를 받을 수 있습니다:

```bash
# 프롬프트 조회
curl "http://localhost:8000/v1/prompt?topic=2025년 디지털 전환 계획"
```

AI가 **Markdown 코드블록**으로만 응답하여, 복사-붙여넣기 시 서식이 유지됩니다.

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 웹 UI |
| POST | `/v1/conversions` | 변환 요청 |
| GET | `/v1/conversions/{id}` | 상태 조회 |
| GET | `/v1/conversions/{id}/download` | 결과 다운로드 |
| GET/POST | `/v1/prompt` | ChatGPT 프롬프트 |
| GET | `/v1/templates` | 템플릿 목록 |
| POST | `/v1/templates` | 템플릿 업로드 |
| GET | `/healthz` | 헬스체크 |

## 프로젝트 구조

```
hwpx-converter/
├── src/
│   └── hwpx_converter/
│       ├── __init__.py      # 패키지 초기화
│       ├── converter.py     # 변환기 코어
│       ├── api.py           # FastAPI 서버
│       ├── cli.py           # 명령행 도구
│       ├── models.py        # 데이터 모델
│       ├── errors.py        # 에러 처리
│       ├── storage.py       # 파일 저장소
│       └── static/          # 웹 UI
│           └── index.html
├── data/
│   ├── templates/           # HWPX 템플릿
│   └── jobs/                # 변환 작업 디렉토리
├── pyproject.toml           # 패키지 설정
└── README.md
```

## 개발

```bash
# 개발 환경 설치
pip install -e ".[dev]"

# 테스트 실행
pytest

# 코드 포맷팅
black src/
ruff check src/
```

## 라이선스

MIT License

## 감사의 말

- [pypandoc-hwpx](https://github.com/msjang/pypandoc-hwpx) - 원본 라이브러리
- [Pandoc](https://pandoc.org) - 문서 변환 엔진
- 경기도의회 AI입법혁신팀

---

**문의**: 경기도의회 공간정보과 AI입법혁신팀
