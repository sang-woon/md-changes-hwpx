/**
 * WysiwygEditor - 통합 WYSIWYG 편집기
 * 마크다운 붙여넣기 → 스타일 미리보기 → 직접 편집
 */
class WysiwygEditor {
    constructor(editorElement, options = {}) {
        this.editor = editorElement;
        this.styleManager = options.styleManager || new StyleManager();
        this.parser = new MarkdownParser(this.styleManager);
        this.rawMarkdown = '';
        this.onChangeCallbacks = [];

        this._init();
    }

    _init() {
        // contenteditable 설정
        this.editor.setAttribute('contenteditable', 'true');
        this.editor.classList.add('wysiwyg-editor');

        // 이벤트 리스너 등록
        this._bindEvents();

        // 플레이스홀더 설정
        this._updatePlaceholder();
    }

    _bindEvents() {
        // 붙여넣기 이벤트: 마크다운 → HTML 변환
        this.editor.addEventListener('paste', (e) => this._handlePaste(e));

        // 입력 이벤트: 변경 감지
        this.editor.addEventListener('input', () => this._handleInput());

        // 포커스/블러: 플레이스홀더 관리
        this.editor.addEventListener('focus', () => this._handleFocus());
        this.editor.addEventListener('blur', () => this._handleBlur());

        // 키보드 단축키
        this.editor.addEventListener('keydown', (e) => this._handleKeydown(e));
    }

    _handlePaste(e) {
        e.preventDefault();

        // 클립보드에서 텍스트 가져오기
        const text = e.clipboardData.getData('text/plain');

        if (!text) return;

        // 마크다운 패턴 감지
        if (this._isMarkdown(text)) {
            this.rawMarkdown = text;
            const html = this.parser.parseToHtml(text);
            this._insertHtml(html);
        } else {
            // 일반 텍스트는 그대로 삽입
            this._insertText(text);
        }

        this._triggerChange();
    }

    _handleInput() {
        this._updatePlaceholder();
        this._triggerChange();
    }

    _handleFocus() {
        this.editor.classList.add('focused');
        if (this.editor.dataset.empty === 'true') {
            this.editor.innerHTML = '';
        }
    }

    _handleBlur() {
        this.editor.classList.remove('focused');
        this._updatePlaceholder();
    }

    _handleKeydown(e) {
        // Ctrl+B: 볼드
        if (e.ctrlKey && e.key === 'b') {
            e.preventDefault();
            document.execCommand('bold', false, null);
        }

        // Ctrl+Z: 실행 취소
        if (e.ctrlKey && e.key === 'z') {
            // 기본 동작 허용
        }

        // Enter: 새 줄에서 동일한 스타일 유지
        if (e.key === 'Enter' && !e.shiftKey) {
            // 기본 동작 허용하되 필요시 커스텀 처리 가능
        }
    }

    _isMarkdown(text) {
        // 마크다운 패턴 감지
        const patterns = [
            /^#+ /m,           // 제목
            /^[-*] /m,         // 리스트
            /^> /m,            // 인용
            /\*\*.+\*\*/,      // 볼드
            /^\s+[-*] /m       // 들여쓰기된 리스트
        ];

        return patterns.some(pattern => pattern.test(text));
    }

    _insertHtml(html) {
        // 현재 선택 위치에 HTML 삽입
        if (this.editor.innerHTML.trim() === '' || this.editor.dataset.empty === 'true') {
            this.editor.innerHTML = html;
        } else {
            // 선택된 위치에 삽입
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                range.deleteContents();

                const fragment = document.createRange().createContextualFragment(html);
                range.insertNode(fragment);
            } else {
                this.editor.innerHTML += html;
            }
        }

        this.editor.dataset.empty = 'false';
    }

    _insertText(text) {
        document.execCommand('insertText', false, text);
    }

    _updatePlaceholder() {
        const isEmpty = this.editor.textContent.trim() === '';
        this.editor.dataset.empty = isEmpty ? 'true' : 'false';
    }

    _triggerChange() {
        // 현재 HTML을 마크다운으로 변환하여 저장
        this.rawMarkdown = this.parser.parseToMarkdown(this.editor.innerHTML);

        // 콜백 호출
        this.onChangeCallbacks.forEach(cb => cb(this.rawMarkdown));
    }

    // Public API

    /**
     * 마크다운 설정
     */
    setMarkdown(markdown) {
        this.rawMarkdown = markdown;
        const html = this.parser.parseToHtml(markdown);
        this.editor.innerHTML = html;
        this._updatePlaceholder();
        this._triggerChange();
    }

    /**
     * 마크다운 가져오기
     */
    getMarkdown() {
        return this.rawMarkdown;
    }

    /**
     * HTML 가져오기 (HWPX 변환용)
     */
    getHtml() {
        return this.editor.innerHTML;
    }

    /**
     * 내용 초기화
     */
    clear() {
        this.editor.innerHTML = '';
        this.rawMarkdown = '';
        this._updatePlaceholder();
    }

    /**
     * 스타일 설정 업데이트 후 재렌더링
     */
    updateStyles(newSettings) {
        this.styleManager.updateSettings(newSettings);
        if (this.rawMarkdown) {
            const html = this.parser.parseToHtml(this.rawMarkdown);
            this.editor.innerHTML = html;
        }
    }

    /**
     * 변경 이벤트 리스너 등록
     */
    onChange(callback) {
        this.onChangeCallbacks.push(callback);
    }

    /**
     * 편집기 포커스
     */
    focus() {
        this.editor.focus();
    }
}

// 전역 내보내기
if (typeof window !== 'undefined') {
    window.WysiwygEditor = WysiwygEditor;
}
