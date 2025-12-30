"""
마크다운 → HWPX 변환 웹 서비스

마크다운을 붙여넣으면 HWPX로 다운로드할 수 있는 웹 서비스입니다.
"""

import os
import uuid
import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 변환기 임포트
import sys
sys.path.insert(0, str(Path(__file__).parent))
from font_converter import OfficialFontConverter

app = FastAPI(title="HWPX 변환 서비스")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 임시 파일 디렉토리
TEMP_DIR = Path(tempfile.gettempdir()) / "hwpx_web"
TEMP_DIR.mkdir(exist_ok=True)

# 템플릿 경로
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "data" / "templates" / "blank.hwpx"

# HTML 템플릿
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>마크다운 → HWPX 변환기</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            color: white;
            padding: 30px 0;
        }
        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .panel-header {
            background: #4a5568;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-body {
            padding: 20px;
        }
        textarea {
            width: 100%;
            height: 300px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            font-family: 'D2Coding', 'Consolas', monospace;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            display: inline-block;
            padding: 15px 40px;
            font-size: 16px;
            font-weight: bold;
            color: white;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .btn-container {
            text-align: center;
            margin-top: 20px;
        }
        .guide {
            background: #f7fafc;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.8;
        }
        .guide h3 {
            color: #4a5568;
            margin-bottom: 10px;
        }
        .guide table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .guide th, .guide td {
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        .guide th {
            background: #edf2f7;
            font-weight: bold;
        }
        .guide code {
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'D2Coding', monospace;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .message {
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            display: none;
        }
        .message.success {
            background: #c6f6d5;
            color: #276749;
        }
        .message.error {
            background: #fed7d7;
            color: #c53030;
        }
        .copy-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: bold;
            color: white;
            background: linear-gradient(135deg, #38a169 0%, #2f855a 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .copy-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(56, 161, 105, 0.4);
        }
        .copy-btn svg {
            width: 18px;
            height: 18px;
        }
        .template-box {
            background: #1a202c;
            color: #a0aec0;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            font-family: 'D2Coding', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-wrap;
            overflow-x: auto;
            position: relative;
        }
        .template-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .chatgpt-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: bold;
            color: white;
            background: linear-gradient(135deg, #10a37f 0%, #0d8a6a 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
        }
        .chatgpt-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(16, 163, 127, 0.4);
        }
        .chatgpt-btn svg {
            width: 20px;
            height: 20px;
        }
        .notice-box {
            background: #fffbeb;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 12px 15px;
            margin-top: 15px;
            font-size: 12px;
            color: #92400e;
        }
        .notice-box strong {
            color: #d97706;
        }
        @media (max-width: 900px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>마크다운 → HWPX 변환기</h1>
            <p>공공기관 보고서 스타일로 자동 변환됩니다</p>
        </header>

        <div class="main-content">
            <!-- 왼쪽: 작성 가이드 -->
            <div class="panel">
                <div class="panel-header">📝 작성 가이드</div>
                <div class="panel-body">
                    <div class="guide">
                        <h3>마크다운 작성 규칙</h3>
                        <table>
                            <tr>
                                <th>마크다운</th>
                                <th>HWPX 출력</th>
                                <th>글꼴</th>
                            </tr>
                            <tr>
                                <td><code># 제목</code></td>
                                <td>Ⅰ. 제목</td>
                                <td>HY헤드라인M 18pt</td>
                            </tr>
                            <tr>
                                <td><code>## 제목</code></td>
                                <td>① 제목</td>
                                <td>함초롱바탕 굵게 15pt</td>
                            </tr>
                            <tr>
                                <td><code>- 항목</code></td>
                                <td>□ 항목</td>
                                <td>함초롱바탕 15pt</td>
                            </tr>
                            <tr>
                                <td><code>&nbsp;&nbsp;&nbsp;&nbsp;- 항목</code></td>
                                <td>   ㅇ 항목</td>
                                <td>함초롱바탕 14pt</td>
                            </tr>
                            <tr>
                                <td><code>> 주석</code></td>
                                <td>   ※ 주석</td>
                                <td>맑은 고딕 10pt</td>
                            </tr>
                        </table>

                        <h3 style="margin-top: 20px;">⚠️ 주의사항</h3>
                        <ul style="margin-left: 20px; line-height: 1.8; margin-top: 10px;">
                            <li><strong>들여쓰기</strong>: 2단계 항목은 반드시 <strong>4칸 공백</strong>으로 들여쓰기</li>
                            <li><strong>볼드체</strong>: <code>**텍스트**</code> 형식으로 강조</li>
                            <li><strong>주석</strong>: <code>&gt;</code> 로 시작 (작은 글씨로 변환)</li>
                            <li><strong>특수문자</strong>: 「」 ~ 등은 그대로 유지됨</li>
                        </ul>
                    </div>

                    <!-- 마크다운 입력 영역 -->
                    <h3 style="margin-top: 20px; color: #4a5568;">✏️ 마크다운 입력</h3>
                    <form id="convertForm" style="margin-top: 10px;">
                        <textarea id="markdown" name="markdown" placeholder="마크다운을 여기에 붙여넣으세요..."></textarea>
                        <input type="text" id="filename" name="filename" value="report"
                               style="width: 100%; padding: 10px; margin-top: 10px; border: 2px solid #e2e8f0; border-radius: 6px;"
                               placeholder="파일명 (확장자 제외)">
                        <div class="btn-container">
                            <button type="submit" class="btn" id="convertBtn">HWPX 변환 및 다운로드</button>
                        </div>
                    </form>
                    <div class="loading" id="loading">
                        <div class="spinner"></div>
                        <p>변환 중...</p>
                    </div>
                    <div class="message" id="message"></div>
                </div>
            </div>

            <!-- 오른쪽: 예시 템플릿 -->
            <div class="panel">
                <div class="panel-header">
                    <span>📋 예시 템플릿</span>
                    <button onclick="copyAndOpenChatGPT()" class="chatgpt-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08-4.778 2.758a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
                        </svg>
                        프롬프트 복사 & ChatGPT 이동
                    </button>
                </div>
                <div class="panel-body">
                    <div class="notice-box">
                        <strong>💡 사용 방법:</strong> 오른쪽 상단 버튼을 클릭하면 프롬프트가 복사되고 ChatGPT로 이동합니다.<br>
                        ChatGPT에서 붙여넣기(Ctrl+V)하면 마크다운 형식의 보고서를 생성해줍니다.
                    </div>

                    <div class="template-header">
                        <h3 style="color: #4a5568;">복사될 프롬프트 내용</h3>
                    </div>
                    <div class="template-box">
<span style="color: #68d391;">공공기관 보고서를 마크다운 형식으로 작성해주세요.</span>
<span style="color: #68d391;">반드시 코드블록(```) 형태로 출력해서 복사할 수 있게 해주세요.</span>

<span style="color: #fc8181;">⚠️ 중요: 결과물은 반드시 "개조식"으로 작성해주세요!</span>
<span style="color: #fc8181;">- 문장형이 아닌 명사형/개조식으로 간결하게 작성</span>
<span style="color: #fc8181;">- 예: "매출이 증가하였습니다" (X) → "매출 증가" (O)</span>
<span style="color: #fc8181;">- 예: "시장 점유율이 확대될 것으로 예상됩니다" (X) → "시장 점유율 확대 전망" (O)</span>

<span style="color: #63b3ed;">주제: [여기에 보고서 주제를 입력하세요]</span>

<span style="color: #f6ad55;">📌 작성 규칙 (반드시 준수):</span>
<span style="color: #a0aec0;">- # 대제목 → Ⅰ. 형태로 변환됨</span>
<span style="color: #a0aec0;">- ## 중제목 → ① 형태로 변환됨</span>
<span style="color: #a0aec0;">- - 1단계 항목 → □ 형태로 변환됨</span>
<span style="color: #a0aec0;">-     - 2단계 항목 (4칸 들여쓰기) → ㅇ 형태로 변환됨</span>
<span style="color: #a0aec0;">- > 주석 → ※ 형태로 변환됨</span>

<span style="color: #b794f4;">📝 예시 형식:</span>
<span style="color: #a0aec0;"># 보고서 제목</span>

<span style="color: #a0aec0;">## 첫 번째 섹션</span>

<span style="color: #a0aec0;">- 주요 항목 내용</span>
<span style="color: #a0aec0;">    - 세부 내용 (4칸 들여쓰기)</span>
<span style="color: #a0aec0;">    - 또 다른 세부 내용</span>

<span style="color: #a0aec0;">> 참고사항이나 주석 내용</span>
                    </div>

                    <div style="margin-top: 20px;">
                        <h3 style="color: #4a5568; margin-bottom: 10px;">📥 입력창에 직접 복사</h3>
                        <button onclick="copyToInput()" class="copy-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                            예시 템플릿을 입력창에 복사
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const chatGPTPrompt = `공공기관 보고서를 마크다운 형식으로 작성해주세요.
반드시 코드블록(\`\`\`) 형태로 출력해서 복사할 수 있게 해주세요.

⚠️ 중요: 결과물은 반드시 "개조식"으로 작성해주세요!
- 문장형이 아닌 명사형/개조식으로 간결하게 작성
- 예: "매출이 증가하였습니다" (X) → "매출 증가" (O)
- 예: "시장 점유율이 확대될 것으로 예상됩니다" (X) → "시장 점유율 확대 전망" (O)

주제: [여기에 보고서 주제를 입력하세요]

📌 작성 규칙 (반드시 준수):
- # 대제목 → Ⅰ. 형태로 변환됨
- ## 중제목 → ① 형태로 변환됨
- - 1단계 항목 → □ 형태로 변환됨
-     - 2단계 항목 (4칸 들여쓰기) → ㅇ 형태로 변환됨
- > 주석 → ※ 형태로 변환됨

📝 예시 형식:
# 보고서 제목

## 첫 번째 섹션

- 주요 항목 내용
    - 세부 내용 (4칸 들여쓰기)
    - 또 다른 세부 내용

> 참고사항이나 주석 내용`;

        const exampleTemplate = `# 보고서 제목을 입력하세요

## 첫 번째 섹션

- 주요 항목 내용
    - 세부 내용 (4칸 들여쓰기)
    - 또 다른 세부 내용

> 참고사항이나 주석 내용

- 다른 주요 항목
    - 세부 내용

## 두 번째 섹션

- 항목 내용
    - 세부 내용`;

        function copyAndOpenChatGPT() {
            navigator.clipboard.writeText(chatGPTPrompt).then(() => {
                const message = document.getElementById('message');
                message.textContent = '프롬프트가 복사되었습니다! ChatGPT로 이동합니다...';
                message.className = 'message success';
                message.style.display = 'block';

                setTimeout(() => {
                    window.open('https://chatgpt.com/', '_blank');
                }, 500);
            }).catch(err => {
                alert('복사에 실패했습니다: ' + err);
            });
        }

        function copyToInput() {
            document.getElementById('markdown').value = exampleTemplate;
            const message = document.getElementById('message');
            message.textContent = '예시 템플릿이 입력창에 복사되었습니다.';
            message.className = 'message success';
            message.style.display = 'block';
            setTimeout(() => { message.style.display = 'none'; }, 2000);
        }

        document.getElementById('convertForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const markdown = document.getElementById('markdown').value;
            const filename = document.getElementById('filename').value || 'report';
            const btn = document.getElementById('convertBtn');
            const loading = document.getElementById('loading');
            const message = document.getElementById('message');

            if (!markdown.trim()) {
                message.textContent = '마크다운을 입력해주세요.';
                message.className = 'message error';
                message.style.display = 'block';
                return;
            }

            btn.disabled = true;
            loading.style.display = 'block';
            message.style.display = 'none';

            try {
                const formData = new FormData();
                formData.append('markdown', markdown);
                formData.append('filename', filename);

                const response = await fetch('/convert', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename + '.hwpx';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();

                    message.textContent = '변환 완료! 파일이 다운로드됩니다.';
                    message.className = 'message success';
                } else {
                    const error = await response.json();
                    message.textContent = '오류: ' + (error.detail || '변환에 실패했습니다.');
                    message.className = 'message error';
                }
            } catch (err) {
                message.textContent = '오류: ' + err.message;
                message.className = 'message error';
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
                message.style.display = 'block';
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    """메인 페이지"""
    return HTML_PAGE


@app.post("/convert")
async def convert_markdown(
    markdown: str = Form(...),
    filename: str = Form(default="report"),
):
    """마크다운을 HWPX로 변환"""

    if not markdown.strip():
        raise HTTPException(status_code=400, detail="마크다운을 입력해주세요.")

    # 고유 ID 생성
    job_id = str(uuid.uuid4())[:8]

    # 입력 파일 저장
    input_path = TEMP_DIR / f"{job_id}_input.md"
    output_path = TEMP_DIR / f"{job_id}_{filename}.hwpx"

    try:
        # 마크다운 저장
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        # 변환
        converter = OfficialFontConverter(template_path=str(TEMPLATE_PATH))
        converter.convert(str(input_path), str(output_path))

        # 파일 반환
        return FileResponse(
            path=str(output_path),
            filename=f"{filename}.hwpx",
            media_type="application/vnd.hancom.hwpx"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 입력 파일 삭제
        if input_path.exists():
            input_path.unlink()


@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


def run():
    """서버 실행"""
    import uvicorn

    print("\n=== HWPX Converter Web Service ===")
    print("Access: http://localhost:8000")
    print("="*35 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
