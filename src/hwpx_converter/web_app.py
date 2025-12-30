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
            max-width: 1200px;
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
        }
        .panel-body {
            padding: 20px;
        }
        textarea {
            width: 100%;
            height: 400px;
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
        .font-info {
            margin-top: 15px;
            padding: 10px;
            background: #ebf8ff;
            border-radius: 6px;
            font-size: 12px;
        }
        .font-info h4 {
            color: #2b6cb0;
            margin-bottom: 8px;
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
            <div class="panel">
                <div class="panel-header">마크다운 입력</div>
                <div class="panel-body">
                    <form id="convertForm">
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

            <div class="panel">
                <div class="panel-header">작성 가이드 & 예시 템플릿</div>
                <div class="panel-body">
                    <div class="guide">
                        <h3>📝 마크다운 작성 규칙</h3>
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
                                <td>ㅇ 항목</td>
                                <td>함초롱바탕 14pt</td>
                            </tr>
                            <tr>
                                <td><code>> 주석</code></td>
                                <td>※ 주석</td>
                                <td>맑은 고딕 10pt</td>
                            </tr>
                        </table>

                        <h3 style="margin-top: 20px;">📋 예시 템플릿 (복사해서 사용하세요)</h3>
                        <div style="background: #1a202c; color: #a0aec0; padding: 15px; border-radius: 8px; margin-top: 10px; font-family: monospace; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-x: auto;">
<span style="color: #68d391;"># 보고서 제목을 입력하세요</span>

<span style="color: #63b3ed;">## 첫 번째 섹션</span>

<span style="color: #f6ad55;">- 주요 항목 내용</span>
<span style="color: #fc8181;">    - 세부 내용 (4칸 들여쓰기)</span>
<span style="color: #fc8181;">    - 또 다른 세부 내용</span>

<span style="color: #b794f4;">> 참고사항이나 주석 내용</span>

<span style="color: #f6ad55;">- 다른 주요 항목</span>
<span style="color: #fc8181;">    - 세부 내용</span>

<span style="color: #63b3ed;">## 두 번째 섹션</span>

<span style="color: #f6ad55;">- 항목 내용</span>
<span style="color: #fc8181;">    - 세부 내용</span>
                        </div>
                        <button onclick="copyTemplate()" class="btn" style="margin-top: 10px; padding: 8px 20px; font-size: 13px;">예시 템플릿 복사</button>

                        <h3 style="margin-top: 20px;">⚠️ 주의사항</h3>
                        <ul style="margin-left: 20px; line-height: 1.8; margin-top: 10px;">
                            <li><strong>들여쓰기</strong>: 2단계 항목은 반드시 <strong>4칸 공백</strong>으로 들여쓰기</li>
                            <li><strong>볼드체</strong>: <code>**텍스트**</code> 형식으로 강조</li>
                            <li><strong>주석</strong>: <code>&gt;</code> 로 시작 (작은 글씨로 변환)</li>
                            <li><strong>특수문자</strong>: 「」 ~ 등은 그대로 유지됨</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
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

        function copyTemplate() {
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
