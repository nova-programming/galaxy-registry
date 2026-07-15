#!/usr/bin/env sh
set -eu

APP_NAME="Nova + Galaxy"
RELEASE_BASE="https://github.com/nova-programming/Nova/releases/download"
NOVA_REPO_ZIP="https://github.com/nova-programming/Nova/archive/refs/heads/main.zip"
ZIP_PREFIX="Nova-main"
INSTALL_DIR="${HOME}/.nova"
ALLOWED_FILES="_galaxy.py nova.nv runtime.c"
ALLOWED_DIRS="bootstrap stdlib tools galaxy"

info()  { printf "  [..]  %s\n" "$1"; }
ok()    { printf "  [OK]  %s\n" "$1"; }
warn()  { printf "  [WARN] %s\n" "$1"; }
fail()  { printf "  [FAIL] %s\n" "$1"; exit 1; }

usage() {
    echo "Usage: sh install.sh              Install"; echo "       sh install.sh --uninstall  Remove"; exit 0
}

add_to_path() {
    cfg="${HOME}/.profile"
    [ -n "${ZSH_VERSION-}" ] && cfg="${HOME}/.zshrc"
    [ -n "${BASH_VERSION-}" ] && [ -f "${HOME}/.bashrc" ] && cfg="${HOME}/.bashrc"
    marker="# Added by Nova installer"
    if [ -f "$cfg" ] && grep -q "$marker" "$cfg" 2>/dev/null; then
        info "PATH already in ${cfg}"; return
    fi
    echo "" >> "$cfg"
    echo "$marker" >> "$cfg"
    echo "export PATH=\"\$PATH:${INSTALL_DIR}\"" >> "$cfg"
    ok "Added PATH to ${cfg}"
    info "Run '. ${cfg}' or restart your terminal."
}

remove_from_path() {
    for f in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.zshrc"; do
        [ -f "$f" ] && sed '/# Added by Nova installer/d;/nova\/bin/d;/\.nova/d' "$f" > "${f}.tmp" 2>/dev/null && mv "${f}.tmp" "$f" 2>/dev/null && ok "Cleaned $f" || true
    done
}

create_launchers() {
    # Probe for python command — prefer python3, fall back to python
    py_cmd="python3"
    command -v python3 >/dev/null 2>&1 || py_cmd="python"
    printf '%s\n' "#!/usr/bin/env ${py_cmd}" 'import sys, os' 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))' 'os.chdir(os.path.dirname(os.path.abspath(__file__)))' 'from bootstrap.main import main; main()' > "${INSTALL_DIR}/nova"
    printf '%s\n' "#!/usr/bin/env ${py_cmd}" 'import sys, os' 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))' 'from _galaxy import main; main()' > "${INSTALL_DIR}/galaxy"
    chmod +x "${INSTALL_DIR}/nova" "${INSTALL_DIR}/galaxy"
    ok "Created launchers"
}

do_install() {
    echo ""; echo "  +========================================+"; echo "  |  Nova + Galaxy Installer               |"; echo "  +========================================+"; echo ""
    info "Install directory: ${INSTALL_DIR}"

    if [ -d "$INSTALL_DIR" ]; then info "Directory exists — will overwrite."; fi
    mkdir -p "$INSTALL_DIR"

    have_curl=0; have_tar=0; have_unzip=0; have_python=0; have_python3=0
    command -v curl >/dev/null 2>&1 && have_curl=1
    command -v tar >/dev/null 2>&1 && have_tar=1
    command -v unzip >/dev/null 2>&1 && have_unzip=1
    command -v python3 >/dev/null 2>&1 && have_python3=1 && have_python=1
    command -v python >/dev/null 2>&1 && have_python=1
    [ "$have_curl" = 0 ] && fail "curl is required. Install curl and try again."
    [ "$have_python" = 0 ] && fail "Python 3 is required. Install python3/python and try again."

    # Try release tarball first (lean, needs only curl+tar)
    downloaded=0
    if [ "$have_tar" = 1 ]; then
        info "Looking up latest release..."
        latest_tag=""
        if [ "$have_python3" = 1 ]; then
            latest_tag=$(curl -fsSL -H "Accept: application/json" "https://api.github.com/repos/nova-programming/Nova/releases/latest" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tag_name',''))" 2>/dev/null || echo "")
        fi
        if [ -n "$latest_tag" ]; then
            info "Fetching release ${latest_tag}..."
            tmpdir="/tmp/nova-install-$$"
            mkdir -p "$tmpdir"
            curl -fsSL -o "${tmpdir}/nova.tar.gz" "${RELEASE_BASE}/${latest_tag}/${latest_tag}.tar.gz" 2>/dev/null && \
            tar xzf "${tmpdir}/nova.tar.gz" -C "$INSTALL_DIR" 2>/dev/null && \
            downloaded=1 && ok "Extracted release tarball"
            rm -rf "$tmpdir"
        else
            info "No release found, using repo zip..."
        fi
    fi

    # Fallback: repo zip with unzip or python3 -m zipfile
    if [ "$downloaded" = 0 ]; then
        info "Trying full repo zip..."
        tmpzip="/tmp/nova-install-$$.zip"
        curl -fsSL -o "$tmpzip" "$NOVA_REPO_ZIP" || fail "Download failed"

        if [ "$have_unzip" = 1 ]; then
            info "Extracting with unzip..."
            tmpdir="/tmp/nova-extract-$$"
            mkdir -p "$tmpdir"
            unzip -q "$tmpzip" -d "$tmpdir"
            for f in $ALLOWED_FILES; do
                [ -f "${tmpdir}/${ZIP_PREFIX}/${f}" ] && cp "${tmpdir}/${ZIP_PREFIX}/${f}" "${INSTALL_DIR}/${f}"
            done
            for d in $ALLOWED_DIRS; do
                [ -d "${tmpdir}/${ZIP_PREFIX}/${d}" ] && cp -r "${tmpdir}/${ZIP_PREFIX}/${d}" "${INSTALL_DIR}/"
            done
            rm -rf "$tmpdir"
            downloaded=1
        elif [ "$have_python" = 1 ]; then
            info "Extracting with python3..."
            python3 -c "
import zipfile, io, os
zf = zipfile.ZipFile('${tmpzip}')
prefix = '${ZIP_PREFIX}/'
allowed_files = set('${ALLOWED_FILES}'.split())
allowed_dirs = set('${ALLOWED_DIRS}'.split())
for name in zf.namelist():
    if not name.startswith(prefix) or name.endswith('/'): continue
    rel = name[len(prefix):]
    top = rel.split('/')[0]
    if top in allowed_files or top in allowed_dirs:
        dst = os.path.join('${INSTALL_DIR}', rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with zf.open(name) as src, open(dst, 'wb') as df:
            df.write(src.read())
zf.close()
" && downloaded=1
        else
            fail "Need unzip or python3 to extract. Install one and re-run."
        fi
        rm -f "$tmpzip"
    fi

    [ "$downloaded" = 0 ] && fail "Extraction failed"

    # Check for GCC (needed by 'nova build')
    if command -v gcc >/dev/null 2>&1; then
        ok "GCC found on PATH"
    else
        warn "GCC not found — 'nova build' will need it."
        warn "Install build-essential (Linux) or Xcode CLI tools (macOS)."
        warn "Or use 'nova dev <file.nv>' (VM mode, no compiler needed)."
    fi

    create_launchers
    add_to_path

    echo ""; echo "  +------------------------------------------------+"; echo "  |  Installed successfully!                         |"; echo "  +------------------------------------------------+"; echo ""
    info "Location: ${INSTALL_DIR}"
    info "Restart your terminal, then:"
    info "  nova --version          Check Nova version"
    info "  nova build hello.nv     Compile a Nova program"
    info "  galaxy --version        Check Galaxy version"
    info "  galaxy install pkg      Install a package"
    echo ""
}

do_uninstall() {
    echo ""; echo "  Uninstalling ${APP_NAME}..."; echo ""
    if [ -d "$INSTALL_DIR" ]; then rm -rf "$INSTALL_DIR"; ok "Removed: ${INSTALL_DIR}"; fi
    remove_from_path; echo ""; ok "${APP_NAME} uninstalled."; echo ""
}

case "${1:-}" in
    --uninstall|uninstall|remove) do_uninstall ;;
    --help|-h) usage ;;
    *) do_install ;;
esac
