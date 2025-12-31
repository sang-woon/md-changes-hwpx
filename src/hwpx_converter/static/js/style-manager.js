/**
 * StyleManager - 스타일 설정 관리 및 CSS 생성
 */
class StyleManager {
    constructor(settings) {
        this.settings = settings || this._getDefaultSettings();
        this.romanNumerals = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ'];
        this.circledNumbers = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩'];
        this.koreanChars = ['가', '나', '다', '라', '마', '바', '사', '아', '자', '차'];
    }

    _getDefaultSettings() {
        return {
            title: { bullet: 'roman', size: 18, bold: true },
            subtitle: { bullet: 'circled', size: 15, bold: true },
            level1: { bullet: '□', size: 15, bold: false },
            level2: { bullet: 'ㅇ', size: 12 },
            note: { bullet: '*', size: 10 }
        };
    }

    updateSettings(newSettings) {
        this.settings = { ...this.settings, ...newSettings };
    }

    getTitlePrefix(counter) {
        const { bullet } = this.settings.title;
        if (bullet === 'roman') return `${this.romanNumerals[counter - 1] || counter}. `;
        if (bullet === 'number') return `${counter}. `;
        return '';
    }

    getSubtitlePrefix(counter) {
        const { bullet } = this.settings.subtitle;
        if (bullet === 'circled') return `${this.circledNumbers[counter - 1] || `(${counter})`} `;
        if (bullet === 'number') return `${counter}) `;
        if (bullet === 'korean') return `${this.koreanChars[counter - 1] || counter}. `;
        return '';
    }

    getBullet(level) {
        if (level === 1) return this.settings.level1.bullet;
        return this.settings.level2.bullet;
    }

    getNoteBullet() {
        const bullet = this.settings.note.bullet;
        return bullet !== 'none' ? bullet + ' ' : '';
    }

    getStyle(type) {
        const config = this.settings[type];
        if (!config) return '';

        const styles = [];
        styles.push(`font-size: ${config.size}pt`);
        if (config.bold) styles.push('font-weight: bold');

        // 타입별 추가 스타일
        if (type === 'title') {
            styles.push('color: #1a365d');
            styles.push('border-bottom: 2px solid #3182ce');
            styles.push('padding-bottom: 0.3em');
            styles.push('margin: 1em 0 0.5em');
        } else if (type === 'subtitle') {
            styles.push('color: #2c5282');
            styles.push('margin: 0.8em 0 0.4em');
        } else if (type === 'level1') {
            styles.push('margin: 0.3em 0');
            styles.push('padding-left: 0.5em');
        } else if (type === 'level2') {
            styles.push('margin: 0.2em 0');
            styles.push('padding-left: 2em');
        } else if (type === 'note') {
            styles.push('color: #718096');
            styles.push('border-left: 3px solid #cbd5e0');
            styles.push('padding-left: 1em');
            styles.push('margin: 0.3em 0');
        }

        return styles.join('; ');
    }

    getListStyle(level) {
        return level === 1 ? this.getStyle('level1') : this.getStyle('level2');
    }
}

// 전역 내보내기
if (typeof window !== 'undefined') {
    window.StyleManager = StyleManager;
}
