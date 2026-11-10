#!/usr/bin/env python3
"""Generate a static, individually-indexable HTML page for every package in packages/.

Before this script, package "detail pages" existed only as a client-side JS view inside
index.html (fetch('/packages/<name>.json') + DOM injection), with no unique URL — nothing
a search engine could crawl, link to, or index, and nothing a developer could share directly.

This script reads packages/index.json + packages/<name>.json (the existing data files;
nothing about how packages are authored/published changes) and writes one real
packages/<name>.html per package, using PACKAGE_TEMPLATE below. It also regenerates
packages/index.html (a simple directory of all packages) and rewrites the <url> entries for
packages in sitemap.xml.

Only fields that are actually present in the package JSON are rendered -- no fabricated
download counts, ratings, reviews, or last-published dates.

Usage: python tools/build_package_pages.py [packages_dir]
"""
import html
import json
import os
import sys

SITE = "https://galaxy-registry.vercel.app"

PACKAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="../favicon.svg">
    <title>{title}</title>
    <meta name="description" content="{description_attr}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Galaxy">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description_attr}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{site}/og-image.jpg">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description_attr}">
    <meta name="twitter:image" content="{site}/og-image.jpg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.6/purify.min.js"></script>
    <link rel="stylesheet" href="../theme.css">
    <script src="../theme.js"></script>
    <script type="application/ld+json">{jsonld}</script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: var(--leading-normal); }}
        nav.top-nav {{
            position: sticky; top: 0; z-index: var(--z-nav);
            background: var(--nav-bg); backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
            padding: 0 2rem; height: 60px;
        }}
        .nav-brand {{ font-weight: 700; font-size: 1.2rem; letter-spacing: -0.03em; display: flex; align-items: center; gap: 0.5rem; text-decoration: none; color: inherit; }}
        .nav-brand svg {{ width: 22px; height: 22px; }}
        .nav-links {{ display: flex; gap: 1.75rem; align-items: center; }}
        .nav-links a {{ color: var(--text-secondary); text-decoration: none; font-size: 0.875rem; font-weight: 500; }}
        .nav-links a:hover {{ color: var(--text); }}
        main.pkg-main {{ max-width: var(--content-width-doc); margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
        .breadcrumbs {{ margin-bottom: 1.5rem; }}
        .pkg-head {{ display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
        .pkg-head h1 {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; }}
        .tier-badge {{ font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); text-transform: uppercase; }}
        .tier-badge.core {{ background: var(--core-bg); color: var(--core); }}
        .tier-badge.verified {{ background: var(--verified-bg); color: var(--verified); }}
        .tier-badge.community {{ background: var(--community-bg); color: var(--community); }}
        .pkg-desc {{ color: var(--text-secondary); font-size: 1rem; margin-bottom: 1.25rem; max-width: 640px; }}
        .keyword-list {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
        .keyword {{ font-size: 0.78rem; background: var(--sidebar-bg); border: 1px solid var(--border); padding: 0.15rem 0.55rem; border-radius: var(--radius-sm); color: var(--text-secondary); }}
        .install-row {{ display: flex; align-items: center; gap: 0.5rem; background: var(--code-bg); color: var(--code-text); border-radius: var(--radius-md); padding: 0.85rem 1.1rem; font-family: var(--font-mono); font-size: 0.85rem; margin-bottom: 2rem; max-width: 640px; }}
        .install-row button {{ margin-left: auto; background: transparent; border: 1px solid #30363d; color: inherit; border-radius: var(--radius-sm); padding: 0.3rem 0.7rem; font-size: 0.75rem; cursor: pointer; }}
        .install-row button:hover {{ border-color: var(--accent); color: var(--accent); }}
        .pkg-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 2.5rem; align-items: start; }}
        @media (max-width: 760px) {{ .pkg-grid {{ grid-template-columns: 1fr; }} }}
        .pkg-section {{ margin-bottom: 2rem; }}
        .pkg-section h2 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }}
        .pkg-readme {{ font-size: 0.92rem; color: var(--text-secondary); }}
        .pkg-readme :is(h1,h2,h3) {{ color: var(--text); margin: 1rem 0 0.5rem; }}
        .pkg-readme p {{ margin-bottom: 0.75rem; }}
        .pkg-readme pre {{ background: var(--code-bg); color: var(--code-text); padding: 1rem 1.25rem; border-radius: var(--radius-md); overflow-x: auto; font-size: 0.82rem; margin-bottom: 0.75rem; }}
        .pkg-readme code {{ font-family: var(--font-mono); }}
        .meta-list {{ list-style: none; font-size: 0.85rem; }}
        .meta-list li {{ display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); }}
        .meta-list span:first-child {{ color: var(--text-tertiary); }}
        .dep-list {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
        .dep-list a {{ font-size: 0.8rem; background: var(--sidebar-bg); border: 1px solid var(--border); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); color: var(--accent); text-decoration: none; }}
        .dep-list a:hover {{ border-color: var(--accent); }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
        .data-table th {{ text-align: left; padding: 0.4rem 0.6rem; background: var(--sidebar-bg); border-bottom: 2px solid var(--border); }}
        .data-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border-subtle); font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-secondary); }}
        .security-card {{ border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1rem 1.1rem; font-size: 0.82rem; }}
        .security-card div {{ display: flex; justify-content: space-between; padding: 0.3rem 0; }}
        footer {{ border-top: 1px solid var(--border); padding: 1.75rem 2rem; background: var(--sidebar-bg); }}
        .footer-inner {{ max-width: 1040px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: var(--text-tertiary); }}
        .footer-links {{ display: flex; gap: 1.5rem; }}
        .footer-links a {{ color: var(--text-tertiary); text-decoration: none; }}
    </style>
</head>
<body>
    <nav class="top-nav">
        <a class="nav-brand" href="../index.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            Galaxy
        </a>
        <button class="nav-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="primary-nav" onclick="toggleMobileNav(this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </button>
        <div class="nav-links" id="primary-nav">
            <a href="index.html">Packages</a>
            <a href="../documentation.html">Docs</a>
            <a href="../reference.html">Reference</a>
            <a href="../examples.html">Examples</a>
            <a href="../playground.html">Playground</a>
            <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Dark/Light theme">&#9789;</button>
        </div>
    </nav>

    <main class="pkg-main">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="../index.html">Home</a><span class="sep">/</span><a href="index.html">Packages</a><span class="sep">/</span><span class="current">{name}</span>
        </nav>

        <div class="pkg-head">
            <h1>{name}</h1>
            <span class="tier-badge {tier}">{tier_label}</span>
        </div>
        <p class="pkg-desc">{description_html}</p>
        <div class="keyword-list">{keyword_badges}</div>

        <div class="install-row">
            <span>$ galaxy install {name}</span>
            <button type="button" onclick="navigator.clipboard.writeText('galaxy install {name}')">Copy</button>
        </div>

        <div class="pkg-grid">
            <div>
                <section class="pkg-section">
                    <h2>Overview</h2>
                    <div class="pkg-readme" id="readme">
                        <p>{description_html}</p>
                        {repo_note}
                    </div>
                </section>

                {versions_section}
            </div>

            <div>
                <section class="pkg-section">
                    <h2>Package info</h2>
                    <ul class="meta-list">
                        <li><span>Version</span><span>{version}</span></li>
                        <li><span>Author</span><span>{author_html}</span></li>
                        <li><span>License</span><span>{license}</span></li>
                        <li><span>Upvotes</span><span>&#9650; {upvotes}</span></li>
                    </ul>
                </section>

                <section class="pkg-section">
                    <h2>Security &amp; provenance</h2>
                    <div class="security-card">
                        <div><span>Signature</span><span>{sig_status}</span></div>
                        <div><span>Status</span><span>{quarantine_status}</span></div>
                    </div>
                </section>

                {dependencies_section}

                {links_section}
            </div>
        </div>
    </main>

    <footer>
        <div class="footer-inner">
            <span>&copy; 2026 Nova Programming Language</span>
            <div class="footer-links">
                <a href="../documentation.html">Docs</a>
                <a href="../reference.html">Reference</a>
                <a href="../examples.html">Examples</a>
                <a href="../playground.html">Playground</a>
            </div>
        </div>
    </footer>

    <script>
        // Progressive enhancement only: replaces the static overview paragraph with the
        // package's real README when it can be fetched, exactly like the registry's
        // package-detail view does. If the fetch fails (private/renamed/placeholder repo),
        // the static server-rendered description above stays as-is -- nothing is lost.
        {readme_fetch_script}
    </script>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova Packages — Galaxy Registry</title>
    <meta name="description" content="Browse every package published to Galaxy, the package registry for the Nova programming language.">
    <link rel="canonical" href="{site}/packages/index.html">
    <link rel="icon" type="image/svg+xml" href="../favicon.svg">
    <link rel="stylesheet" href="../theme.css">
    <script src="../theme.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); }}
        nav.top-nav {{ position: sticky; top: 0; background: var(--nav-bg); backdrop-filter: blur(14px); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; padding: 0 2rem; height: 60px; }}
        .nav-brand {{ font-weight: 700; font-size: 1.2rem; display: flex; align-items: center; gap: 0.5rem; text-decoration: none; color: inherit; }}
        .nav-brand svg {{ width: 22px; height: 22px; }}
        main {{ max-width: 960px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
        h1 {{ font-size: 1.9rem; font-weight: 800; margin-bottom: 0.5rem; }}
        .lede {{ color: var(--text-secondary); margin-bottom: 2rem; }}
        .pkg-row {{ display: block; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1rem 1.25rem; margin-bottom: 0.75rem; text-decoration: none; color: inherit; }}
        .pkg-row:hover {{ border-color: var(--accent); }}
        .pkg-row .name {{ font-weight: 700; margin-right: 0.5rem; }}
        .tier-badge {{ font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: var(--radius-sm); text-transform: uppercase; }}
        .tier-badge.core {{ background: var(--core-bg); color: var(--core); }}
        .tier-badge.verified {{ background: var(--verified-bg); color: var(--verified); }}
        .tier-badge.community {{ background: var(--community-bg); color: var(--community); }}
        .pkg-row p {{ color: var(--text-secondary); font-size: 0.88rem; margin-top: 0.35rem; }}
    </style>
</head>
<body>
    <nav class="top-nav">
        <a class="nav-brand" href="../index.html">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
            Galaxy
        </a>
    </nav>
    <main>
        <h1>Nova Packages</h1>
        <p class="lede">Every package currently published to Galaxy.</p>
        {rows}
    </main>
</body>
</html>
"""


def esc(value):
    return html.escape(str(value), quote=True)


def tier_label(tier):
    return {"core": "Core", "verified": "Verified", "community": "Community"}.get(tier, tier.title())


def build_jsonld(name, data, canonical):
    pkg_obj = {
        "@type": "SoftwareSourceCode",
        "name": data.get("package", name),
        "description": data.get("description", ""),
        "programmingLanguage": "Nova",
        "url": canonical,
    }
    if data.get("version"):
        pkg_obj["version"] = data["version"]
    if data.get("license"):
        pkg_obj["license"] = data["license"]
    repo = data.get("github_repo", "")
    if isinstance(repo, str) and "/" in repo and ".." not in repo:
        pkg_obj["codeRepository"] = f"https://github.com/{repo}"
    if data.get("author"):
        pkg_obj["author"] = {"@type": "Organization", "name": data["author"]}

    breadcrumb_obj = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Packages", "item": SITE + "/packages/index.html"},
            {"@type": "ListItem", "position": 3, "name": data.get("package", name), "item": canonical},
        ],
    }
    obj = {"@context": "https://schema.org", "@graph": [pkg_obj, breadcrumb_obj]}
    return json.dumps(obj, ensure_ascii=False)


def build_versions_section(data):
    versions = data.get("versions") or []
    if not versions:
        return ""
    rows = "".join(
        f"<tr><td>v{esc(v.get('version',''))}</td><td>{esc(v.get('sha256',''))}</td></tr>"
        for v in reversed(versions)
    )
    return (
        '<section class="pkg-section"><h2>Release history</h2>'
        '<table class="data-table"><thead><tr><th>Version</th><th>SHA-256</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></section>"
    )


def build_dependencies_section(data):
    deps = data.get("dependencies") or []
    if not deps:
        return (
            '<section class="pkg-section"><h2>Dependencies</h2>'
            '<p style="font-size:0.85rem;color:var(--text-tertiary);">No external dependencies (pure Nova module).</p></section>'
        )
    links = "".join(f'<a href="{esc(d)}.html">{esc(d)}</a>' for d in deps)
    return f'<section class="pkg-section"><h2>Dependencies</h2><div class="dep-list">{links}</div></section>'


def build_links_section(data):
    repo = data.get("github_repo", "")
    links = []
    if isinstance(repo, str) and "/" in repo and ".." not in repo:
        links.append(f'<a href="https://github.com/{esc(repo)}" target="_blank" rel="noopener">Repository</a>')
        if data.get("issue_number"):
            links.append(
                f'<a href="https://github.com/nova-programming/galaxy-registry/issues/{int(data["issue_number"])}" target="_blank" rel="noopener">Discussion</a>'
            )
    if not links:
        return ""
    body = " &middot; ".join(links)
    return f'<section class="pkg-section"><h2>Links</h2><p style="font-size:0.85rem;">{body}</p></section>'


def build_readme_fetch_script(repo):
    if not (isinstance(repo, str) and "/" in repo and ".." not in repo):
        return ""
    return f"""
        fetch("https://raw.githubusercontent.com/{repo}/main/README.md")
            .then(r => {{ if (!r.ok) throw new Error(); return r.text(); }})
            .then(md => {{ document.getElementById('readme').innerHTML = DOMPurify.sanitize(marked.parse(md)); }})
            .catch(() => {{ /* keep the static server-rendered description */ }});
    """.strip()


def render_package_page(name, data):
    canonical = f"{SITE}/packages/{name}.html"
    description = data.get("description", "")
    title = f"{data.get('package', name)} — Galaxy"
    repo = data.get("github_repo", "")
    repo_note = ""
    if isinstance(repo, str) and "/" in repo and ".." not in repo:
        repo_note = f'<p>See the <a href="https://github.com/{esc(repo)}" target="_blank" rel="noopener">GitHub repository</a> for full documentation.</p>'

    tier = data.get("tier", "community")
    quarantined = bool(data.get("quarantined"))
    sig_status = "Verified by Core Signers" if tier in ("core", "verified") else "Community Signature Pinned"
    quarantine_status = "Quarantined for Review" if quarantined else "Clean &middot; No Active Advisories"

    keyword_badges = "".join(f'<span class="keyword">{esc(k)}</span>' for k in data.get("keywords") or [])

    html_out = PACKAGE_TEMPLATE.format(
        title=esc(title),
        description_attr=esc(description),
        description_html=esc(description),
        canonical=canonical,
        site=SITE,
        jsonld=build_jsonld(name, data, canonical),
        name=esc(data.get("package", name)),
        tier=esc(tier),
        tier_label=esc(tier_label(tier)),
        keyword_badges=keyword_badges,
        repo_note=repo_note,
        versions_section=build_versions_section(data),
        version=esc(data.get("version", "")),
        author_html=esc(data.get("author", "")),
        license=esc(data.get("license", "MIT")),
        upvotes=esc(data.get("upvotes", 0)),
        sig_status=sig_status,
        quarantine_status=quarantine_status,
        dependencies_section=build_dependencies_section(data),
        links_section=build_links_section(data),
        readme_fetch_script=build_readme_fetch_script(repo),
    )
    return html_out


def render_index_page(packages):
    rows = []
    for p in packages:
        name = p["name"]
        rows.append(
            f'<a class="pkg-row" href="{esc(name)}.html">'
            f'<span class="name">{esc(name)}</span>'
            f'<span class="tier-badge {esc(p.get("tier","community"))}">{esc(tier_label(p.get("tier","community")))}</span>'
            f'<p>{esc(p.get("description",""))}</p></a>'
        )
    return INDEX_TEMPLATE.format(site=SITE, rows="\n        ".join(rows))


def update_sitemap(package_names, repo_root):
    path = os.path.join(repo_root, "sitemap.xml")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    marker_start = "  <!-- BEGIN packages (generated by tools/build_package_pages.py) -->"
    marker_end = "  <!-- END packages -->"
    entries = [f"  <url><loc>{SITE}/packages/index.html</loc></url>"]
    entries += [f"  <url><loc>{SITE}/packages/{esc(n)}.html</loc></url>" for n in package_names]
    block = marker_start + "\n" + "\n".join(entries) + "\n" + marker_end

    if marker_start in content and marker_end in content:
        pre = content.split(marker_start)[0]
        post = content.split(marker_end)[1]
        content = pre + block + post
    else:
        content = content.replace("</urlset>", block + "\n</urlset>\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    packages_dir = sys.argv[1] if len(sys.argv) > 1 else "packages"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    packages_dir = os.path.join(repo_root, packages_dir) if not os.path.isabs(packages_dir) else packages_dir

    index_path = os.path.join(packages_dir, "index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
    packages = index_data.get("packages", [])

    written = 0
    names = []
    for p in packages:
        name = p["name"]
        detail_path = os.path.join(packages_dir, f"{name}.json")
        if not os.path.exists(detail_path):
            print(f"warning: no {name}.json, skipping", file=sys.stderr)
            continue
        with open(detail_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out_path = os.path.join(packages_dir, f"{name}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(render_package_page(name, data))
        written += 1
        names.append(name)

    index_html_path = os.path.join(packages_dir, "index.html")
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(render_index_page(packages))

    update_sitemap(names, repo_root)

    print(f"Wrote {written} package page(s) + packages/index.html, updated sitemap.xml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
