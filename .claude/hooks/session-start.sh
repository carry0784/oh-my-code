#!/bin/bash
# SessionStart hook: install the Claude Code tools (8 tools + Karpathy guidelines) and the project's
# test environment in cloud sessions.
# Idempotent: each step is skipped when already installed.
# One failing step does not stop the others.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

log() { echo "[session-start] $*" >&2; }
step() { local name="$1"; shift; if "$@"; then log "OK   $name"; else log "FAIL $name"; fi; }

# --- Claude plugins -----------------------------------------------------------
has_plugin() { claude plugin list 2>/dev/null | grep -q "> $1\$"; }
has_market() { claude plugin marketplace list 2>/dev/null | grep -q "> $1\$"; }

install_plugin() { # <plugin@market> <market name> <market source>
  has_plugin "$1" && return 0
  has_market "$2" || claude plugin marketplace add "$3" >&2 || return 1
  claude plugin install "$1" >&2
}

step superpowers install_plugin superpowers@claude-plugins-official claude-plugins-official anthropics/claude-plugins-official
step mattpocock-skills install_plugin mattpocock-skills@claude-plugins-official claude-plugins-official anthropics/claude-plugins-official
step addyosmani-agent-skills install_plugin agent-skills@addy-agent-skills addy-agent-skills https://github.com/addyosmani/agent-skills.git
step ecc install_plugin ecc@ecc ecc https://github.com/affaan-m/ECC.git
step karpathy-skills install_plugin andrej-karpathy-skills@karpathy-skills karpathy-skills https://github.com/multica-ai/andrej-karpathy-skills.git

# --- skills CLI (user-level skills) ------------------------------------------
install_skills() { # <repo> <marker skill dir>
  [ -d "$HOME/.claude/skills/$2" ] && return 0
  (cd "$HOME" && npx -y skills add "$1" -g -y >&2)
  [ -d "$HOME/.claude/skills/$2" ]
}

step archify install_skills tt-a1i/archify archify
step vercel-agent-skills install_skills vercel-labs/agent-skills vercel-react-best-practices

# --- gstack -------------------------------------------------------------------
GSTACK="$HOME/.claude/skills/gstack"

install_gstack() {
  if [ ! -x "$GSTACK/setup" ]; then
    git clone --single-branch --depth 1 -q https://github.com/garrytan/gstack.git "$GSTACK" || return 1
  fi
  [ -x "$GSTACK/browse/dist/browse" ] && return 0
  # Setup's Chromium download fails behind the proxy; everything else installs.
  (cd "$GSTACK" && ./setup >&2)
  [ -x "$GSTACK/browse/dist/browse" ]
}

# The Playwright CDN is blocked, so point gstack's Playwright revision at the
# Chromium build pre-installed in /opt/pw-browsers (originals are not modified).
link_gstack_chromium() {
  local root="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}" want src_rev want_rev d f
  want=$(cd "$GSTACK" && bun -e 'console.log(require("./node_modules/playwright").chromium.executablePath())') || return 1
  [ -x "$want" ] && return 0
  want_rev=$(echo "$want" | sed -n 's#.*/chromium-\([0-9]*\)/.*#\1#p')
  src_rev=$(ls -d "$root"/chromium-[0-9]* 2>/dev/null | grep -v "chromium-$want_rev\$" | sed 's#.*-##' | sort -n | tail -1)
  [ -n "$want_rev" ] && [ -n "$src_rev" ] || return 1

  mkdir -p "$root/chromium-$want_rev"
  ln -sfn "$root/chromium-$src_rev/chrome-linux" "$root/chromium-$want_rev/chrome-linux64"
  cp "$root/chromium-$src_rev"/{INSTALLATION_COMPLETE,DEPENDENCIES_VALIDATED} "$root/chromium-$want_rev/" 2>/dev/null

  d="$root/chromium_headless_shell-$want_rev/chrome-headless-shell-linux64"
  mkdir -p "$d"
  for f in "$root/chromium_headless_shell-$src_rev/chrome-linux"/*; do ln -sfn "$f" "$d/$(basename "$f")"; done
  ln -sfn "$root/chromium_headless_shell-$src_rev/chrome-linux/headless_shell" "$d/chrome-headless-shell"
  cp "$root/chromium_headless_shell-$src_rev"/{INSTALLATION_COMPLETE,DEPENDENCIES_VALIDATED} "$root/chromium_headless_shell-$want_rev/" 2>/dev/null

  [ -x "$want" ]
}

step gstack install_gstack
step gstack-chromium link_gstack_chromium

# --- REA ----------------------------------------------------------------------
install_rea() {
  grep -q '"rea"' "$HOME/.claude.json" 2>/dev/null && return 0
  (cd "$HOME" && npx -y rea-agents setup --client claude_code --yes >/dev/null 2>&1)
  grep -q '"rea"' "$HOME/.claude.json" 2>/dev/null
}

step rea install_rea

# --- Project test environment (mirrors .github/workflows/ci.yml) --------------
install_test_env() {
  cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || return 1
  python -m pip install -q -r requirements.txt aiosqlite ruff==0.15.9 >&2 &&
    python -m pip install -q -e . >&2 || return 1
  # A preinstalled uv-tool ruff shadows pip's on PATH; pin it to CI's version.
  if command -v uv >/dev/null && uv tool list 2>/dev/null | grep -q '^ruff '; then
    uv tool list | grep -q '^ruff v0.15.9$' || uv tool install -q --force ruff==0.15.9 >&2
  fi
}

step test-env install_test_env

exit 0
