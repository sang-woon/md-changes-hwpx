# pypandoc-hwpx 공공기관 스타일 확장

마크다운(Markdown) 문서를 경기도의회 등 공공기관의 보고서 스타일에 맞는 HWPX(한글 문서) 파일로 변환하는 Python 라이브러리입니다.

## 📋 주요 기능

- **공공기관 표준 글머리 기호**: □ → ○ → - 형태의 계층 구조 자동 적용
- **레벨별 폰트 크기**: Level 1(15pt), Level 2(13pt), Level 3(11pt) 자동 설정
- **참조 템플릿 지원**: 기존 HWPX 파일의 스타일을 상속하여 일관된 서식 유지
- **REST API 서비스**: FastAPI 기반 웹 서비스로 손쉬운 통합 가능

## 🚀 설치 방법

### 필수 요구사항

```bash
# Pandoc 설치 (필수)
sudo apt-get install pandoc  # Ubuntu/Debian
brew install pandoc          # macOS

# Python 패키지 설치
pip install pypandoc-hwpx
pip install fastapi uvicorn  # API 서버 사용 시
```

### 저장소에서 설치

```bash
git clone https://github.com/your-repo/pypandoc-hwpx-official.git
cd pypandoc-hwpx-official
pip install -e .
```

## 📖 사용 방법

### 1. Python 코드에서 직접 사용

```python
from src.official_converter import OfficialHwpxConverter

# 변환기 초기화
converter = OfficialHwpxConverter()

# 마크다운 → HWPX 변환
converter.convert('report.md', 'report.hwpx')
```

### 2. 커스텀 스타일 적용

```python
from src.official_converter import OfficialHwpxConverter

# 커스텀 글머리 기호 및 폰트 크기 설정
converter = OfficialHwpxConverter(
    bullets={
        1: '□',   # Level 1
        2: '○',   # Level 2
        3: '▪',   # Level 3
    },
    font_sizes={
        1: 1600,  # 16pt
        2: 1400,  # 14pt
        3: 1200,  # 12pt
    }
)

converter.convert('report.md', 'report.hwpx')
```

### 3. 참조 템플릿 사용

```python
from src.official_converter import OfficialHwpxConverter

# 기존 HWPX 파일의 스타일을 참조하여 변환
converter = OfficialHwpxConverter(
    reference_hwpx='template.hwpx'  # 스타일 참조 파일
)

converter.convert('report.md', 'report.hwpx')
```

### 4. 명령행 도구 사용

```bash
# 기본 변환
python -m src.official_converter report.md -o report.hwpx

# 참조 템플릿 지정
python -m src.official_converter report.md -o report.hwpx --reference template.hwpx
```

### 5. REST API 서버 실행

```bash
# 서버 시작
cd src
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# API 문서 확인
# http://localhost:8000/docs
```

## 📝 마크다운 작성 규칙

공공기관 보고서 스타일에 맞게 변환하려면 다음과 같이 마크다운을 작성합니다:

```markdown
# Ⅰ. 대제목 (Header 1 → 개요 1)

## 1 중제목 (Header 2 → 개요 2)

- 1단계 항목 (□ 15pt)
    - 2단계 항목 (○ 13pt)
        - 3단계 항목 (- 11pt)

## 2 다른 중제목

- 또 다른 항목
    - 세부 내용
```

### 변환 결과 예시

```
Ⅰ. 대제목
  1 중제목
    □ 1단계 항목 (15pt)
      ○ 2단계 항목 (13pt)
        - 3단계 항목 (11pt)
```

## 🔧 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 서비스 상태 확인 |
| GET | `/api/styles` | 기본 스타일 정보 조회 |
| POST | `/api/convert/text` | 마크다운 텍스트 변환 |
| POST | `/api/convert/file` | 마크다운 파일 업로드 및 변환 |
| GET | `/api/download/{file_id}` | 변환된 파일 다운로드 |

### API 사용 예시

```python
import requests

# 텍스트 변환
response = requests.post(
    'http://localhost:8000/api/convert/text',
    json={
        'markdown': '# 제목\n\n- 항목 1\n    - 세부 항목',
        'filename': 'report'
    }
)

result = response.json()
download_url = result['download_url']

# 파일 다운로드
file_response = requests.get(f'http://localhost:8000{download_url}')
with open('report.hwpx', 'wb') as f:
    f.write(file_response.content)
```

## 📁 프로젝트 구조

```
pypandoc-hwpx-official/
├── src/
│   ├── official_converter.py      # 메인 변환기
│   ├── official_template_generator.py  # 템플릿 생성기
│   └── api_server.py              # FastAPI 서버
├── blank.hwpx                     # 기본 템플릿
├── test_report.md                 # 테스트용 마크다운
└── README.md
```

## 🤝 기여하기

1. 이 저장소를 Fork합니다
2. 새 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some amazing feature'`)
4. 브랜치에 Push합니다 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성합니다

## 📄 라이선스

MIT License

## 🙏 감사의 말

- [pypandoc-hwpx](https://github.com/msjang/pypandoc-hwpx) - 원본 라이브러리
- [Pandoc](https://pandoc.org) - 문서 변환 엔진
- 경기도의회 AI입법혁신팀

---

**문의**: 경기도의회 의정포털 공간정보과 AI입법혁신팀
