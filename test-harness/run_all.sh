#!/usr/bin/env bash
#
# Run integration tests for all Surf SDKs.
#
# Usage:
#   SURF_API_TEST_TOKEN=surf_sk_live_... ./test-harness/run_all.sh
#
# Optional:
#   SURF_API_BASE_URL=https://api.surf.social  (default)
#   SDKS="python typescript go java"           (default: all)
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "${SURF_API_TEST_TOKEN:-}" ]; then
    echo "ERROR: SURF_API_TEST_TOKEN is required"
    echo "Usage: SURF_API_TEST_TOKEN=surf_sk_live_... $0"
    exit 1
fi

export SURF_API_TEST_TOKEN
export SURF_API_BASE_URL="${SURF_API_BASE_URL:-https://api.surf.social/v1}"

SDKS="${SDKS:-python typescript go java}"
PASSED=()
FAILED=()
SKIPPED=()

run_python() {
    echo "═══════════════════════════════════════════"
    echo "  Python SDK"
    echo "═══════════════════════════════════════════"
    cd "$ROOT/../py-services/apps/devportal"
    if ! command -v python3 &>/dev/null; then
        echo "  SKIP: python3 not found"
        SKIPPED+=("python")
        return
    fi
    if python3 -m pytest tests/ -v --tb=short 2>&1; then
        PASSED+=("python")
    else
        FAILED+=("python")
    fi
    echo
}

run_typescript() {
    echo "═══════════════════════════════════════════"
    echo "  TypeScript SDK"
    echo "═══════════════════════════════════════════"
    cd "$ROOT/typescript"
    if ! command -v npx &>/dev/null; then
        echo "  SKIP: npx not found"
        SKIPPED+=("typescript")
        return
    fi
    if npx tsx tests/integration.test.ts 2>&1; then
        PASSED+=("typescript")
    else
        FAILED+=("typescript")
    fi
    echo
}

run_go() {
    echo "═══════════════════════════════════════════"
    echo "  Go SDK"
    echo "═══════════════════════════════════════════"
    cd "$ROOT/go"
    if ! command -v go &>/dev/null; then
        echo "  SKIP: go not found"
        SKIPPED+=("go")
        return
    fi
    if go test -tags integration -v -count=1 ./... 2>&1; then
        PASSED+=("go")
    else
        FAILED+=("go")
    fi
    echo
}

run_java() {
    echo "═══════════════════════════════════════════"
    echo "  Java SDK"
    echo "═══════════════════════════════════════════"
    cd "$ROOT/java"
    if [ ! -f "./gradlew" ]; then
        echo "  SKIP: gradlew not found"
        SKIPPED+=("java")
        return
    fi
    if ./gradlew integrationTest -PSURF_API_TEST_TOKEN="$SURF_API_TEST_TOKEN" \
        ${SURF_API_BASE_URL:+-PSURF_API_BASE_URL="$SURF_API_BASE_URL"} 2>&1; then
        PASSED+=("java")
    else
        FAILED+=("java")
    fi
    echo
}

# Run each SDK sequentially (parallel would hit rate limits)
for sdk in $SDKS; do
    case "$sdk" in
        python)     run_python ;;
        typescript) run_typescript ;;
        go)         run_go ;;
        java)       run_java ;;
        *)          echo "Unknown SDK: $sdk"; SKIPPED+=("$sdk") ;;
    esac
done

# Summary
echo "═══════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════"
[ ${#PASSED[@]} -gt 0 ]  && echo "  PASSED:  ${PASSED[*]}"
[ ${#FAILED[@]} -gt 0 ]  && echo "  FAILED:  ${FAILED[*]}"
[ ${#SKIPPED[@]} -gt 0 ] && echo "  SKIPPED: ${SKIPPED[*]}"
echo

if [ ${#FAILED[@]} -gt 0 ]; then
    exit 1
fi
