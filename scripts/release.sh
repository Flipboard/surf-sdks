#!/usr/bin/env bash
#
# Cut a surf-sdks release. All four SDKs share one version number.
#
#   scripts/release.sh <version> [--dry-run] [--no-push] [--skip-tests]
#   scripts/release.sh 1.2.0
#
# What it does, in order:
#   1. Preflight: valid semver, on `main`, clean tree, (optionally) tests green.
#   2. Bump the version in all version files (Python, TypeScript, Java; Go uses
#      the git tag, so no file) AND the in-code version strings each SDK reports
#      (Python __version__, and the User-Agent in TypeScript, Go and Java). Keeps
#      them in lock-step — this is what stops the "tagged vX but files still say
#      vY" drift (the UA strings sat at 1.0.0 through v1.2.0).
#   3. Roll the CHANGELOG: rename `## Unreleased` -> `## v<version> -- <date>` and
#      open a fresh empty `## Unreleased`.
#   4. Commit "Release v<version>", annotate-tag `v<version>`, and (unless
#      --no-push) push the commit + tag. The tag push triggers .github/workflows/
#      release.yml (GitHub Release + Discord announcement).
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
DRY_RUN=false; NO_PUSH=false; SKIP_TESTS=false
for arg in "${@:2}"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-push) NO_PUSH=true ;;
    --skip-tests) SKIP_TESTS=true ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

[ -n "$VERSION" ] || die "usage: scripts/release.sh <version> [--dry-run] [--no-push] [--skip-tests]"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be semver X.Y.Z (got '$VERSION')"

TAG="v$VERSION"
DATE="$(date -u +%Y-%m-%d)"

# --- 1. Preflight ---
git rev-parse --git-dir >/dev/null 2>&1 || die "not a git repo"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || die "must release from 'main' (on '$BRANCH')"
[ -z "$(git status --porcelain)" ] || die "working tree is dirty — commit or stash first"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"
grep -q "^## v$VERSION " CHANGELOG.md && die "CHANGELOG already has a v$VERSION section"

# Unreleased must have content, else there's nothing to release.
UNREL="$(awk '/^## Unreleased/{f=1;next} /^## v/{f=0} f' CHANGELOG.md | grep -c '[^[:space:]]' || true)"
[ "$UNREL" -gt 0 ] || die "CHANGELOG '## Unreleased' section is empty — nothing to release"

if [ "$SKIP_TESTS" = true ]; then
  echo "==> skipping tests (--skip-tests)"
elif [ -n "${SURF_API_TEST_TOKEN:-}" ] && [ -x test-harness/run_all.sh ]; then
  echo "==> running full test suite (SURF_API_TEST_TOKEN set)"
  ./test-harness/run_all.sh || die "tests failed"
else
  # run_all.sh hard-requires SURF_API_TEST_TOKEN (it exits non-zero without it),
  # so we can't run it here. Warn and continue rather than block the release.
  echo "==> WARNING: SURF_API_TEST_TOKEN not set — skipping the integration suite."
  echo "    For a fully-verified release run: SURF_API_TEST_TOKEN=surf_sk_live_... $0 $VERSION"
  echo "    (continuing; pass --skip-tests to silence this warning)"
fi

# --- 2. Bump versions in lock-step ---
echo "==> bumping all SDKs to $VERSION"
# Python
python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
p = "python/pyproject.toml"
s = open(p).read()
s2 = re.sub(r'(?m)^version\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"', f'version = "{v}"', s, count=1)
assert s != s2, "pyproject.toml version not updated"
open(p, "w").write(s2)
PY
# TypeScript
python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
p = "typescript/package.json"
s = open(p).read()
s2 = re.sub(r'"version"\s*:\s*"[0-9]+\.[0-9]+\.[0-9]+"', f'"version": "{v}"', s, count=1)
assert s != s2, "package.json version not updated"
open(p, "w").write(s2)
PY
# Java
python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
p = "java/build.gradle"
s = open(p).read()
s2 = re.sub(r"(?m)^version\s*=\s*'[0-9]+\.[0-9]+\.[0-9]+'", f"version = '{v}'", s, count=1)
assert s != s2, "build.gradle version not updated"
open(p, "w").write(s2)
PY

# In-code version strings (what the SDKs report about themselves at runtime).
python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
def bump(path, pattern, repl):
    s = open(path).read()
    s2, n = re.subn(pattern, repl, s)
    assert n >= 1, f"{path}: pattern not found"
    open(path, "w").write(s2)
bump("python/src/surf_api/__init__.py", r'(?m)^__version__\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"', f'__version__ = "{v}"')
bump("typescript/src/index.ts",  r"surf-api-ts/[0-9]+\.[0-9]+\.[0-9]+",   f"surf-api-ts/{v}")
bump("go/surf.go",               r'surf-api-go/[0-9]+\.[0-9]+\.[0-9]+',   f"surf-api-go/{v}")
bump("java/src/main/java/social/surf/api/SurfClient.java", r'surf-api-java/[0-9]+\.[0-9]+\.[0-9]+', f"surf-api-java/{v}")
PY

# --- 3. Roll the CHANGELOG ---
echo "==> rolling CHANGELOG (Unreleased -> $TAG -- $DATE)"
python3 - "$VERSION" "$DATE" <<'PY'
import sys
v, date = sys.argv[1], sys.argv[2]
p = "CHANGELOG.md"
s = open(p).read()
marker = "## Unreleased\n"
i = s.index(marker)
head = s[: i + len(marker)]
rest = s[i + len(marker):]
# leave Unreleased empty, insert the versioned header before the moved content
new = head + f"\n## v{v} -- {date}\n" + rest
open(p, "w").write(new)
PY

# --- 4. Commit, tag, push ---
if [ "$DRY_RUN" = true ]; then
  echo "==> --dry-run: changes made but NOT committed. Diff:"
  git --no-pager diff -- python/pyproject.toml typescript/package.json java/build.gradle CHANGELOG.md \
    python/src/surf_api/__init__.py typescript/src/index.ts go/surf.go java/src/main/java/social/surf/api/SurfClient.java
  echo "==> (dry run) would: git commit -m 'Release $TAG'; git tag -a $TAG; git push origin main --follow-tags"
  exit 0
fi

git add python/pyproject.toml typescript/package.json java/build.gradle CHANGELOG.md \
  python/src/surf_api/__init__.py typescript/src/index.ts go/surf.go java/src/main/java/social/surf/api/SurfClient.java
git commit -m "Release $TAG"
git tag -a "$TAG" -m "Release $TAG"
echo "==> committed + tagged $TAG"

if [ "$NO_PUSH" = true ]; then
  echo "==> --no-push: run 'git push origin main --follow-tags' when ready"
else
  git push origin main --follow-tags
  echo "==> pushed. The $TAG tag triggers .github/workflows/release.yml (GitHub Release + Discord)."
fi
