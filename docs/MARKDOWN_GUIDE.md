# 공공기관 보고서 마크다운 작성 가이드

이 가이드는 마크다운(.md) 파일을 공공기관 보고서 스타일의 HWPX 파일로 변환할 때 사용하는 작성 규칙을 설명합니다.

## 📋 서식 매핑 규칙

| 마크다운 입력 | HWPX 출력 | 설명 |
|--------------|-----------|------|
| `# 제목` | Ⅰ. 제목 | 대제목 (로마숫자) |
| `## 제목` | ① 제목 | 중제목 (동그라미 숫자) |
| `- 항목` | □ 항목 | 1단계 항목 (13pt) |
| `    - 항목` | ㅇ 항목 | 2단계 항목 (12pt) |
| `> 내용` | * 내용 | 주석 (10pt) |
| `**굵게**` | **굵게** | 볼드체 유지 |

## ✍️ 작성 예시

### 마크다운 입력 (report.md)

```markdown
# '25년 평가 및 향후 업무추진방향

## '25년 성과 및 보완점

- 교육·돌봄에 대한 **국가책임의 강화**
    - 국가책임형 유아 교육·보육 실현과 **학부모 양육비 부담 경감**을 위해 영유아특별회계 신설('25.12.)하고, 무상교육·보육 **단계적 지원** 확대

> '25년 7월부터 만 5세 무상교육·보육 실시, '26년 지원 대상을 만 4~5세로 확대 예정

    - 고교 무상교육 재원을 안정적으로 지원하기 위해 **국가와 지자체가 분담**하는 「지방교육재정교부금법」 특례 연장('25.8.)

- **국가균형성장을 위한 지방대학 육성 기반 마련**
    - 거점국립대를 5극3특 전략과 연계한 교육·연구 허브로 혁신하고 **지방대학의 경쟁력을 제고**하기 위한 사회적 의제 설정 및 재정 확보

> 거점국립대 교육혁신 지원, 연구중심대학 육성 등을 위한 '26년 예산 총 3조 1,448억 원 편성

## 향후 추진방향

- **디지털 대전환과 인공지능(AI) 시대에 대비**
    - 누구도 소외되지 않는 생애주기 맞춤형 AI교육 추진
```

### HWPX 출력 결과

```
Ⅰ. '25년 평가 및 향후 업무추진방향

① '25년 성과 및 보완점

□ 교육·돌봄에 대한 국가책임의 강화
  ㅇ 국가책임형 유아 교육·보육 실현과 학부모 양육비 부담 경감을 위해 
     영유아특별회계 신설('25.12.)하고, 무상교육·보육 단계적 지원 확대

  * '25년 7월부터 만 5세 무상교육·보육 실시, '26년 지원 대상을 만 4~5세로 확대 예정

  ㅇ 고교 무상교육 재원을 안정적으로 지원하기 위해 국가와 지자체가 
     분담하는 「지방교육재정교부금법」 특례 연장('25.8.)

□ 국가균형성장을 위한 지방대학 육성 기반 마련
  ㅇ 거점국립대를 5극3특 전략과 연계한 교육·연구 허브로 혁신하고 
     지방대학의 경쟁력을 제고하기 위한 사회적 의제 설정 및 재정 확보

  * 거점국립대 교육혁신 지원, 연구중심대학 육성 등을 위한 '26년 예산 총 3조 1,448억 원 편성

② 향후 추진방향

□ 디지털 대전환과 인공지능(AI) 시대에 대비
  ㅇ 누구도 소외되지 않는 생애주기 맞춤형 AI교육 추진
```

## 🔧 사용 방법

### Python 코드에서 사용

```python
from src.official_report_converter import OfficialReportConverter

# 변환기 초기화
converter = OfficialReportConverter()

# 파일 변환
converter.convert('report.md', 'report.hwpx')

# 또는 텍스트 직접 변환
markdown_text = """
# 제목
## 중제목
- 항목 1
    - 세부 항목
"""
converter.convert_text(markdown_text, 'output.hwpx')
```

### 명령행에서 사용

```bash
# 기본 변환
python -m src.official_report_converter report.md -o report.hwpx

# 참조 템플릿 지정
python -m src.official_report_converter report.md -o report.hwpx --reference template.hwpx

# 전처리 없이 변환 (이미 서식이 적용된 마크다운)
python -m src.official_report_converter report.md -o report.hwpx --no-preprocess

# 작성 가이드 확인
python -m src.official_report_converter --guide
```

## ⚠️ 주의사항

1. **들여쓰기**: 2단계 항목은 반드시 4칸 공백으로 들여쓰기해야 합니다.
2. **볼드체**: `**텍스트**` 형식으로 강조할 부분을 표시합니다.
3. **주석**: `>` 로 시작하는 줄은 작은 글씨의 주석으로 변환됩니다.
4. **특수문자**: 「」 (낫표), ~ 등 특수문자는 그대로 유지됩니다.

## 📁 파일 구조

```
project/
├── src/
│   ├── official_report_converter.py  # 메인 변환기
│   ├── official_converter.py         # 기본 변환기
│   └── api_server.py                 # REST API 서버
├── blank.hwpx                        # 기본 템플릿
├── template.hwpx                     # 커스텀 템플릿 (선택)
└── report.md                         # 마크다운 원본
```

## 🎨 스타일 커스터마이징

### 글머리 기호 변경

```python
converter = OfficialReportConverter()

# 글머리 기호 커스터마이징
converter.BULLETS = {
    1: '■',   # 1단계
    2: '●',   # 2단계
    3: '▸',   # 3단계
}
```

### 동그라미 숫자 스타일 변경

```python
# 특수 폰트 동그라미 사용 (기본)
converter = OfficialReportConverter(use_alt_circled=False)
# 결과: 󰊱 󰊲 󰊳

# 일반 동그라미 숫자 사용
converter = OfficialReportConverter(use_alt_circled=True)
# 결과: ① ② ③
```

---

**문의**: 경기도의회 공간정보과 AI입법혁신팀
