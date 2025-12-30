## 1) PRD (Product Requirements Document)

### 1.1 제품 개요

* **제품명(가칭)** : Hangul Document Manager – Markdown to HWPX Converter
* **목적** : Markdown(md) 문서를 공공기관 표준 한글 서식(HWPX)으로 자동 변환하여 **보고서 작성·결재 문서 생산 효율을 개선**한다.
* **핵심 가치**
  * 서식 통제(글꼴/폰트크기/글머리표/제목 체계)를 템플릿으로 표준화
  * 내용은 Markdown으로 간결하게 작성
  * 결과물은 한글(HWPX)로 즉시 활용(수정 최소화)

### 1.2 대상 사용자 및 사용 시나리오

* **대상 사용자**
  * 공공기관 문서 작성자(정책/기획/보고/의회 지원)
  * 문서 서식 담당자(서식 표준 관리)
* **주요 시나리오**
  1. 사용자가 md 파일 업로드 → 변환 템플릿 선택(또는 기본 템플릿 자동) → HWPX 다운로드
  2. 조직 표준 템플릿(글꼴 HY헤드라인M, 1수준 □ 15pt / 2수준 ○ 13pt 등) 유지
  3. 변환 실패 시 에러 로그/원인 안내 및 재시도

### 1.3 범위(Scope)

* **In-Scope (MVP)**
  * md → HWPX 변환(서식: 템플릿 기반)
  * 제목 구조(#, ##) 스타일 적용
  * 목록 계층(-, 들여쓰기) → 글머리표(□/○) 및 폰트 크기 매핑
  * 파일 업로드/다운로드 API
  * 변환 이력(누가/언제/무슨 템플릿/성공·실패) 로그
* **Out-of-Scope (추후)**
  * HWPX → md 양방향 완성도 고도화
  * 박스(“개선 필요사항”) 등 특수 레이아웃 자동 생성(Lua Filter 기반)
  * 전자결재 결재란/머리말·꼬리말 자동 삽입
  * 문서 비교/버전 관리/협업 편집

### 1.4 기능 요구사항 (Functional Requirements)

#### FR-01 변환 요청

* md 파일 업로드로 변환 작업 생성
* 템플릿 선택: 기본 템플릿(조직 표준) 1개 제공, 선택형 다중 템플릿 확장 가능
* 변환 옵션(초기 고정)
  * reference-doc(template.hwpx) 강제 적용

#### FR-02 변환 결과 제공

* 변환 완료 시 HWPX 파일 다운로드
* 실패 시 오류 코드/원인 메시지 제공(사용자 이해 가능한 수준)

#### FR-03 서식 매핑(핵심)

* 제목
  * `#` → 제목 1(HY헤드라인M 등)
  * `##` → 제목 2
* 목록(계층)
  * 1수준 리스트 → `□` / 15pt
  * 2수준 리스트 → `○` / 13pt

    ※ 실제 서식은 template.hwpx에서 정의되며 서비스는 템플릿을 정확히 참조해야 함.

#### FR-04 이력/감사 로그

* 변환 요청/결과(성공·실패), 사용자 식별자, 시간, 파일명, 템플릿 버전 저장

#### FR-05 템플릿 관리(관리자)

* 템플릿 업로드/버전 관리(최소: 파일 교체 및 버전 문자열)
* 기본 템플릿 지정

### 1.5 비기능 요구사항 (Non-Functional Requirements)

* **NFR-01 성능** : 일반 보고서(md 1~3MB) 변환 평균 10초 이내(환경에 따라 조정)
* **NFR-02 가용성** : 업무시간 내 안정 운영(서비스 장애 시 변환 불가 최소화)
* **NFR-03 보안**
  * 업로드 파일 저장 기간 정책(예: 24시간 자동 삭제)
  * 접근제어(내부망/SSO 연계 가능성 고려)
  * 로그에 문서 본문 저장 금지(메타데이터 중심)
* **NFR-04 호환성**
  * Pandoc 버전 고정(서식 결과 일관성)
  * Linux 서버 운영 기준(컨테이너 권장)
* **NFR-05 신뢰성**
  * 템플릿 기반 서식 재현의 일관성 최우선
  * 실패 케이스 재현 가능하도록 오류 로그 표준화

### 1.6 성공 지표(KPI)

* 변환 성공률(예: 95% 이상)
* 변환 후 수동 서식 수정 시간 감소(예: 50% 이상)
* 월간 활성 사용자 / 월간 변환 건수
* 주요 오류 유형 Top N 감소 추세

### 1.7 리스크 및 대응

* **R-01** Pandoc/HWPX 변환 품질 편차 → Pandoc 버전 고정 + 템플릿 엄격 관리
* **R-02** 특정 레이아웃(박스/표 복잡) 미지원 → Out-of-scope로 분리, Lua Filter 단계적 도입
* **R-03** 문서 보안 이슈 → 저장 기간/암호화/접근제어/로그 최소화

---

## 2) TRD (Technical Requirements Document)

### 2.1 기술 개요

* **핵심 원리** : `pandoc` + `pypandoc-hwpx` 실행 시 `--reference-doc=template.hwpx`를 강제하여 **서식을 템플릿으로 통제**
* **런타임 구성**
  * API: FastAPI (Python)
  * 변환 엔진: pandoc 바이너리 + pypandoc-hwpx
  * 작업 실행: 동기(초기) 또는 비동기(확장: Celery/RQ)
  * 저장소: 로컬 디스크(초기) 또는 오브젝트 스토리지(확장)
  * 로그/이력: RDB(PostgreSQL) 또는 최소 로깅(초기 파일 기반)

### 2.2 시스템 아키텍처(권장)

* **MVP(단일 서비스)**
  * FastAPI + 변환 모듈(서버 내 pandoc 실행)
  * 저장: `/data/uploads`, `/data/outputs`
  * 템플릿: `/data/templates/template.hwpx` (버전 폴더)
* **확장(권장)**
  * API 서버 ↔ 작업 큐(비동기) ↔ 변환 워커 분리
  * 대용량/동시 요청 대응

### 2.3 기술 스택

* Python 3.11+
* FastAPI, Uvicorn
* pypandoc-hwpx
* pandoc (버전 고정)
* (선택) PostgreSQL + SQLAlchemy
* (선택) Redis + RQ/Celery (비동기)

### 2.4 변환 파이프라인(처리 흐름)

1. 사용자 업로드(md)
2. 입력 검증(확장자/크기/악성 문자열 최소 점검)
3. 작업ID 발급 및 저장(파일/DB)
4. 변환 실행
   * `pandoc` 호출(라이브러리 경유)
   * `--reference-doc={template.hwpx}`
5. 결과 파일 저장
6. 상태 업데이트(성공/실패 + 오류코드)
7. 다운로드 제공

### 2.5 API 설계(초안)

#### API-01 변환 요청

* `POST /v1/conversions`
* Request (multipart/form-data)
  * `file`: md 파일
  * `template_id`(optional): 기본값 `default`
* Response (JSON)
  * `conversion_id`
  * `status`: `queued|processing|succeeded|failed`
  * `created_at`

#### API-02 변환 상태 조회

* `GET /v1/conversions/{conversion_id}`
* Response
  * `status`
  * `error_code`(optional)
  * `error_message`(optional)
  * `output_ready`(boolean)

#### API-03 결과 다운로드

* `GET /v1/conversions/{conversion_id}/download`
* Response
  * `application/zip` 또는 `application/octet-stream` (hwpx)

#### API-04 템플릿 목록(관리자)

* `GET /v1/templates`
* Response: 템플릿 메타(버전, 적용일)

#### API-05 템플릿 업로드(관리자)

* `POST /v1/templates`
* 파일: hwpx
* 주의: 업로드 즉시 검증(샘플 md로 변환 테스트)

### 2.6 데이터 모델(초안)

* **Template**
  * `template_id` (PK)
  * `version`
  * `file_path`
  * `is_default`
  * `created_at`
* **ConversionJob**
  * `conversion_id` (PK)
  * `user_id`(식별자)
  * `template_id`
  * `input_filename`
  * `input_path`
  * `output_path`
  * `status`
  * `error_code`, `error_message`
  * `created_at`, `finished_at`

### 2.7 서식 구현 세부(필수 규칙)

* Markdown에 `□`, `○`를 직접 넣는 방식은 금지(서식 일관성 저하)
* 리스트 계층으로만 표현
  * 1수준: `- item`
  * 2수준: `    - item`
* 서식은 템플릿에서 정의
  * 1수준 글머리표: □ / 15pt (중고딕)
  * 2수준 글머리표: ○ / 13pt (함초롬바탕)
* 제목 폰트(HY헤드라인M 등)도 템플릿 스타일로 고정

### 2.8 예외/오류 처리 표준

* 오류 분류(예)
  * `E_PANDOC_NOT_FOUND`
  * `E_CONVERSION_FAILED`
  * `E_TEMPLATE_INVALID`
  * `E_INPUT_TOO_LARGE`
  * `E_UNSUPPORTED_MARKDOWN`
* 사용자 메시지(업무용)
  * “템플릿 서식이 유효하지 않습니다(스타일/글머리표 설정 확인 필요).”
  * “입력 문서 구조가 표준 규칙과 다릅니다(목록 들여쓰기 확인).”

### 2.9 보안/운영 요구사항

* 저장 정책: 입력/출력 파일 **자동 삭제(예: 24시간)**
* 접근제어: 내부망/SSO 연계 고려(최소: API Key 또는 프록시 인증)
* 실행 보안:
  * pandoc 실행은 서버 권한 최소화(컨테이너 비root 권장)
  * 업로드 파일 경로/파일명 정규화(경로 조작 방지)
* 로그:
  * 본문 내용 저장 금지
  * 메타데이터 + 오류 스택(민감정보 마스킹)만 기록

### 2.10 배포(권장안)

* Docker 이미지 1개(내부 레지스트리)
* 이미지에 pandoc 포함(버전 고정)
* 볼륨 마운트:
  * `/data/templates`
  * `/data/jobs`
* 헬스체크:
  * `/healthz` (pandoc 실행 가능 여부 포함)

### 2.11 테스트 계획(필수)

* 단위 테스트
  * md 파서 규칙(리스트 계층, 제목)
  * 템플릿 존재/읽기 권한
* 통합 테스트
  * 샘플 md → hwpx 변환 결과 생성 여부
  * 실패 케이스(깨진 템플릿, pandoc 미설치 등)
* 회귀 테스트(서식 품질)
  * 기준 문서 10종을 gold set으로 고정하고 결과 비교
