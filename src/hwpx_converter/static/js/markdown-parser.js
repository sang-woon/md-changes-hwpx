/**
 * MarkdownParser - Markdown ↔ HTML 양방향 변환
 */
class MarkdownParser {
    constructor(styleManager) {
        this.styleManager = styleManager;
        this.titleCounter = 0;
        this.subtitleCounter = 0;
    }

    resetCounters() {
        this.titleCounter = 0;
        this.subtitleCounter = 0;
    }

    /**
     * Markdown → HTML 변환 (미리보기용)
     */
    parseToHtml(markdown) {
        this.resetCounters();
        const lines = markdown.split('\n');
        const htmlParts = [];

        for (const line of lines) {
            const trimmed = line.trim();
            const stripped = line.trimStart();

            // 빈 줄
            if (trimmed === '') {
                htmlParts.push('<div class="empty-line">&nbsp;</div>');
                continue;
            }

            // 제목: # → 로마자
            if (stripped.startsWith('# ') && !stripped.startsWith('## ')) {
                this.titleCounter++;
                this.subtitleCounter = 0; // 소제목 카운터 리셋
                const content = this.processBold(stripped.substring(2));
                const prefix = this.styleManager.getTitlePrefix(this.titleCounter);
                htmlParts.push(this._createTitleHtml(prefix, content));
                continue;
            }

            // 소제목: ## → 원숫자
            if (stripped.startsWith('## ')) {
                this.subtitleCounter++;
                const content = this.processBold(stripped.substring(3));
                const prefix = this.styleManager.getSubtitlePrefix(this.subtitleCounter);
                htmlParts.push(this._createSubtitleHtml(prefix, content));
                continue;
            }

            // 리스트: - 또는 * → 스페이스 + 글머리
            if (stripped.startsWith('- ') || stripped.startsWith('* ')) {
                const indent = line.length - line.trimStart().length;
                const content = this.processBold(stripped.substring(2));

                if (indent >= 2) {
                    // 2단계: 들여쓰기 2칸 이상
                    htmlParts.push(this._createLevel2Html(content));
                } else {
                    // 1단계
                    htmlParts.push(this._createLevel1Html(content));
                }
                continue;
            }

            // 인용/주석: > → 주석 스타일
            if (stripped.startsWith('> ')) {
                const content = this.processBold(stripped.substring(2));
                htmlParts.push(this._createNoteHtml(content));
                continue;
            }

            // 일반 텍스트
            const content = this.processBold(trimmed);
            htmlParts.push(`<div class="paragraph" data-type="text">${content}</div>`);
        }

        return htmlParts.join('\n');
    }

    /**
     * HTML → Markdown 변환 (내보내기용)
     */
    parseToMarkdown(html) {
        const container = document.createElement('div');
        container.innerHTML = html;
        const lines = [];

        for (const child of container.children) {
            const type = child.dataset.type;
            let text = this._htmlToText(child.innerHTML);

            switch (type) {
                case 'title':
                    // 접두사(로마자 등) 제거
                    text = this._removePrefix(text, /^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ\d]+\.\s*/);
                    lines.push(`# ${text}`);
                    break;
                case 'subtitle':
                    // 접두사(원숫자 등) 제거
                    text = this._removePrefix(text, /^[①②③④⑤⑥⑦⑧⑨⑩\d)가나다라마바사아자차]+[.)\s]?\s*/);
                    lines.push(`## ${text}`);
                    break;
                case 'level1':
                    // 글머리(□, ○ 등) 제거
                    text = this._removePrefix(text, /^[□○●◆▪▶ㅇ]\s*/);
                    lines.push(`- ${text}`);
                    break;
                case 'level2':
                    // 글머리 제거
                    text = this._removePrefix(text, /^[□○●◆▪▶ㅇ]\s*/);
                    lines.push(`  - ${text}`);
                    break;
                case 'note':
                    // 주석 기호(*) 제거
                    text = this._removePrefix(text, /^\*\s*/);
                    lines.push(`> ${text}`);
                    break;
                default:
                    if (child.classList.contains('empty-line')) {
                        lines.push('');
                    } else {
                        lines.push(text);
                    }
            }
        }

        return lines.join('\n');
    }

    /**
     * 볼드 처리: **text** → <strong>text</strong>
     */
    processBold(text) {
        return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    }

    /**
     * HTML에서 텍스트 추출 (볼드 유지)
     */
    _htmlToText(html) {
        // strong → **
        let text = html.replace(/<strong>(.+?)<\/strong>/g, '**$1**');
        // 기타 HTML 태그 제거
        text = text.replace(/<[^>]+>/g, '');
        // HTML 엔티티 디코딩
        text = this._decodeHtmlEntities(text);
        return text.trim();
    }

    _decodeHtmlEntities(text) {
        const textarea = document.createElement('textarea');
        textarea.innerHTML = text;
        return textarea.value;
    }

    _removePrefix(text, pattern) {
        return text.replace(pattern, '');
    }

    // HTML 생성 헬퍼 메서드
    _createTitleHtml(prefix, content) {
        const style = this.styleManager.getStyle('title');
        return `<div class="title" data-type="title" style="${style}">${prefix}${content}</div>`;
    }

    _createSubtitleHtml(prefix, content) {
        const style = this.styleManager.getStyle('subtitle');
        return `<div class="subtitle" data-type="subtitle" style="${style}">${prefix}${content}</div>`;
    }

    _createLevel1Html(content) {
        const style = this.styleManager.getStyle('level1');
        const bullet = this.styleManager.getBullet(1);
        return `<div class="level1" data-type="level1" style="${style}"> ${bullet} ${content}</div>`;
    }

    _createLevel2Html(content) {
        const style = this.styleManager.getStyle('level2');
        const bullet = this.styleManager.getBullet(2);
        return `<div class="level2" data-type="level2" style="${style}">   ${bullet} ${content}</div>`;
    }

    _createNoteHtml(content) {
        const style = this.styleManager.getStyle('note');
        const bullet = this.styleManager.getNoteBullet();
        return `<div class="note" data-type="note" style="${style}">${bullet}${content}</div>`;
    }
}

// 전역 내보내기
if (typeof window !== 'undefined') {
    window.MarkdownParser = MarkdownParser;
}
