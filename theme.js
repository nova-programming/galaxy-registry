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

    // ===== Shared mobile navigation (hamburger menu) =====
    function closeMobileNav() {
        document.querySelectorAll('.nav-links.mobile-open').forEach(el => el.classList.remove('mobile-open'));
        document.querySelectorAll('.nav-toggle[aria-expanded="true"]').forEach(btn => btn.setAttribute('aria-expanded', 'false'));
        document.body.classList.remove('nav-open');
    }
    window.closeMobileNav = closeMobileNav;

    window.toggleMobileNav = function(btn) {
        const nav = btn.closest('nav');
        const links = nav && nav.querySelector('.nav-links');
        if (!links) return;
        const opening = !links.classList.contains('mobile-open');
        if (opening) {
            links.classList.add('mobile-open');
            btn.setAttribute('aria-expanded', 'true');
            document.body.classList.add('nav-open');
            const firstLink = links.querySelector('a, button');
            if (firstLink) firstLink.focus();
        } else {
            closeMobileNav();
            btn.focus();
        }
    };

    document.addEventListener('click', (e) => {
        // Close the mobile menu after any nav link/button is activated.
        const links = e.target.closest('.nav-links');
        if (links && links.classList.contains('mobile-open') && (e.target.closest('a') || e.target.closest('button:not(.theme-toggle-btn)'))) {
            closeMobileNav();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeMobileNav();
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 860) closeMobileNav();
    });

    // ===== "Run in Playground" buttons on code blocks =====
    // documentation.html already injects these itself (kept as-is, untouched). This
    // extends the same behavior to reference/examples/templates, which didn't have it,
    // so every real runnable snippet links out to the Playground, not just docs ones.
    function addRunButtons() {
        const blocks = document.querySelectorAll('.doc-content pre, .content pre, .example-body pre');
        blocks.forEach(pre => {
            if (pre.querySelector('.doc-run-btn')) return;
            const text = pre.innerText.trim();
            if (!text || text.startsWith('$') || text.startsWith('curl') || text.startsWith('powershell') ||
                text.startsWith('galaxy ') || text.startsWith('nova ') || text.startsWith('call ') ||
                text.startsWith('//') || text.startsWith('#') || text.startsWith('{')) return;
            if (text.length < 15) return;
            const cs = getComputedStyle(pre);
            if (cs.position === 'static') pre.style.position = 'relative';
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'doc-run-btn';
            btn.innerHTML = '&#9654; Run in Playground';
            btn.title = 'Open this snippet in Nova Playground';
            btn.addEventListener('click', () => {
                const encoded = btoa(encodeURIComponent(text));
                window.open(`playground.html#code=${encoded}`, '_blank');
            });
            pre.appendChild(btn);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addRunButtons);
    } else {
        addRunButtons();
    }

    // ===== Copy-to-clipboard buttons on code blocks =====
    // Runs on documentation/reference/examples/templates. Skips any <pre> this page has
    // already marked (data-no-copy) or that's inside the Playground's own Monaco editor.

    // Fallback for when the async Clipboard API is unavailable or its permission is
    // denied (common in embedded/automated browsers, older browsers, or insecure
    // contexts) -- selects the text in a hidden textarea and uses the older
    // execCommand('copy'), which needs no permission prompt. If even that fails, the
    // user still gets honest feedback instead of a button that silently does nothing.
    function selectText(el) {
        try {
            const range = document.createRange();
            range.selectNodeContents(el);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        } catch (e) { /* no-op */ }
    }

    function fallbackCopy(code, done) {
        try {
            const ta = document.createElement('textarea');
            ta.value = code.innerText;
            ta.style.cssText = 'position:fixed;top:-1000px;left:-1000px;opacity:0;';
            document.body.appendChild(ta);
            ta.select();
            ta.setSelectionRange(0, ta.value.length);
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            if (ok) { done('Copied!'); return; }
        } catch (e) { /* fall through to manual-selection path below */ }
        // Both copy mechanisms failed (e.g. permissions policy blocks both in this
        // embedded context) -- select the code so the user can copy it themselves.
        selectText(code);
        done('Selected — press Ctrl+C');
    }

    function addCopyButtons() {
        const blocks = document.querySelectorAll('.doc-content pre, .content pre, .example-body pre');
        blocks.forEach(pre => {
            if (pre.querySelector('.copy-code-btn') || pre.closest('[data-no-copy]')) return;
            const code = pre.querySelector('code');
            if (!code) return;
            const cs = getComputedStyle(pre);
            if (cs.position === 'static') pre.style.position = 'relative';
            const hasRunBtn = !!pre.querySelector('.doc-run-btn');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'copy-code-btn';
            btn.setAttribute('aria-label', 'Copy code to clipboard');
            btn.textContent = 'Copy';
            btn.style.cssText =
                'position:absolute;top:0.6rem;' + (hasRunBtn ? 'left:0.6rem;' : 'right:0.6rem;') +
                'background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:#e4e4e7;' +
                'font-size:0.72rem;font-weight:600;padding:0.25rem 0.65rem;border-radius:var(--radius-sm);' +
                'cursor:pointer;transition:all 0.15s ease;';
            btn.setAttribute('aria-live', 'polite');
            btn.addEventListener('click', () => {
                const done = (label) => {
                    btn.textContent = label;
                    setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(code.innerText).then(() => done('Copied!'), () => fallbackCopy(code, done));
                } else {
                    fallbackCopy(code, done);
                }
            });
            pre.appendChild(btn);
        });
    }
    // Guard against theme.js executing after DOMContentLoaded/load have already fired
    // (e.g. a script re-run, or a non-standard navigation) -- addEventListener silently
    // never calls back for an event that already happened, so check readyState first.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addCopyButtons);
    } else {
        addCopyButtons();
    }
    // documentation.html injects "Run in Playground" buttons itself, slightly after
    // DOMContentLoaded in some load orders -- a second pass catches those too, without
    // duplicating buttons on blocks already handled.
    if (document.readyState === 'complete') {
        addCopyButtons();
    } else {
        window.addEventListener('load', addCopyButtons);
    }

    // ===== Collapsible docs sidebar (mobile) =====
    // Works regardless of the per-page sidebar class name (.doc-sidebar or .sidebar)
    // or whether it has an id — toggles whichever sidebar the clicked head belongs to.
    window.toggleDocSidebar = function(headEl) {
        const head = (headEl && headEl.nodeType) ? headEl : (event && event.currentTarget);
        const sidebar = head && head.closest('.doc-sidebar, .sidebar');
        if (!sidebar) return;
        const expanded = sidebar.classList.toggle('expanded');
        head.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    };
})();

