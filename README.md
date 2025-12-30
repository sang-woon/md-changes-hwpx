# HWPX Converter

마크다운(Markdown) 문서를 공공기관 보고서 스타일의 HWPX(한글 문서) 파일로 변환하는 Python 라이브러리입니다.

## 주요 기능

- **공공기관 표준 서식**: Ⅰ.→①→□→ㅇ 형태의 계층 구조 자동 적용
- **레벨별 폰트 크기**: 대제목(18pt), 중제목(15pt), 1단계(13pt), 2단계(12pt)
- **참조 템플릿 지원**: 기존 HWPX 파일의 스타일을 상속
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

### 1. Python 코드

```python
from hwpx_converter import HwpxConverter

# 변환기 초기화
converter = HwpxConverter()

# 마크다운 → HWPX 변환
converter.convert('report.md', 'report.hwpx')
```

### 2. 명령행 도구

```bash
# 기본 변환
hwpx-convert report.md -o report.hwpx

# 참조 템플릿 지정
hwpx-convert report.md -o report.hwpx --template custom.hwpx

# 마크다운 작성 가이드 확인
hwpx-convert --guide
```

### 3. REST API 서버

```bash
# 서버 시작
hwpx-server

# 또는
uvicorn hwpx_converter.api:app --host 0.0.0.0 --port 8000

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

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/v1/conversions` | 변환 요청 |
| GET | `/v1/conversions/{id}` | 상태 조회 |
| GET | `/v1/conversions/{id}/download` | 결과 다운로드 |
| GET | `/v1/templates` | 템플릿 목록 |
| POST | `/v1/templates` | 템플릿 업로드 |
| GET | `/healthz` | 헬스체크 |

### API 사용 예시

```python
import requests

# 1. 변환 요청
response = requests.post(
    'http://localhost:8000/v1/conversions',
    data={
        'markdown': '# 제목\n\n- 항목 1\n    - 세부 항목',
        'filename': 'report'
    }
)
result = response.json()
conversion_id = result['conversion_id']

# 2. 상태 확인
status = requests.get(f'http://localhost:8000/v1/conversions/{conversion_id}')
print(status.json())

# 3. 파일 다운로드
if status.json()['output_ready']:
    file_response = requests.get(
        f'http://localhost:8000/v1/conversions/{conversion_id}/download'
    )
    with open('report.hwpx', 'wb') as f:
        f.write(file_response.content)
```

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
│       └── storage.py       # 파일 저장소
├── data/
│   ├── templates/           # HWPX 템플릿
│   └── jobs/                # 변환 작업 디렉토리
├── tests/                   # 테스트
├── docs/                    # 문서 (참조용 원본 코드)
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
