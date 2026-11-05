// Universal Theme Manager for Galaxy Registry Ecosystem
(function() {
    const STORAGE_KEY = 'nova_theme';
    const ALT_STORAGE_KEY = 'nova_playground_theme';

    function getPreferredTheme() {
        const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(ALT_STORAGE_KEY);
        if (stored === 'light' || stored === 'dark') return stored;
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'dark'; // Modern developer ecosystem default: sleek dark theme
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (document.body) {
            document.body.setAttribute('data-theme', theme);
        }
        localStorage.setItem(STORAGE_KEY, theme);
        localStorage.setItem(ALT_STORAGE_KEY, theme);

        document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            btn.innerHTML = theme === 'dark' ? '&#9789;' : '&#9788;';
            btn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
            btn.title = `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`;
        });

        if (window.monaco && window.editor) {
            monaco.editor.setTheme(theme === 'dark' ? 'vs-dark' : 'vs');
        }
    }

    window.toggleTheme = function() {
        const current = (document.body && document.body.getAttribute('data-theme')) || 
                        document.documentElement.getAttribute('data-theme') || 
                        getPreferredTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    };

    // Apply immediately to prevent FOUC
    const initialTheme = getPreferredTheme();
    document.documentElement.setAttribute('data-theme', initialTheme);
    if (document.body) {
        document.body.setAttribute('data-theme', initialTheme);
    }
    document.addEventListener('DOMContentLoaded', () => {
        applyTheme(getPreferredTheme());
    });
})();

