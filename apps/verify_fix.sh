#!/usr/bin/env bash
# RISU P3: isolated developer replay with explicit dependency-download consent.
set -euo pipefail
usage() {
  echo 'Usage: bash apps/verify_fix.sh --allow-build-downloads [--output /new/folder]' >&2
  echo '   or: bash apps/verify_fix.sh --reuse-image risu-v096-real-apps [--output /new/folder]' >&2
}
MODE=''
IMAGE=''
DEST=''
while (($#)); do
  case "$1" in
    --allow-build-downloads) [[ -z "$MODE" ]] || { usage;exit 2; };MODE=build;shift;;
    --reuse-image) [[ -z "$MODE" && $# -ge 2 ]] || { usage;exit 2; };MODE=reuse;IMAGE="$2";shift 2;;
    --output) [[ $# -ge 2 ]] || { usage;exit 2; };DEST="$2";shift 2;;
    *) usage;exit 2;;
  esac
done
[[ -n "$MODE" ]] || { usage;exit 2; }
command -v docker >/dev/null || { echo 'Docker required' >&2;exit 2; }
command -v python >/dev/null || { echo 'Python required' >&2;exit 2; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "$DEST" ]];then DEST="$REPO/risu-v096-p3-replay";fi
[[ ! -e "$DEST" ]] || { echo 'Refusing to overwrite output' >&2;exit 2; }
mkdir -p "$(dirname "$DEST")"
DEST="$(cd "$(dirname "$DEST")" && pwd)/$(basename "$DEST")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/repo" "$TMP/results/repro_package/fixtures" "$TMP/results/repro_package/control_fixtures"
# Host-owned writable parents allow a nonroot (uid 65534) container to write
# files while still letting the developer delete its temporary directory.
chmod 0777 "$TMP/results" "$TMP/results/repro_package" "$TMP/results/repro_package/fixtures" "$TMP/results/repro_package/control_fixtures"
if [[ "$MODE" == build ]];then
  command -v git >/dev/null && command -v tar >/dev/null || { echo 'git/tar required' >&2;exit 2; }
  # Only approved tracked source. No untracked credentials enter Docker context.
  git -C "$REPO" archive HEAD ci apps product_v10 product_v11 product_v12 product_v13 product_v14 triad | tar -x -C "$TMP/repo"
  cd "$TMP/repo"
  python ci/export_v09_source_portable.py
  python ci/upgrade_v10_modules.py
  python ci/upgrade_v11_semantics.py
  python ci/upgrade_v12_decision_witness.py
  python ci/upgrade_v13_repro.py
  python ci/upgrade_v14_fixverify.py
  python -m compileall -q dist/risu_v09_source apps
  IMAGE="risu-v096-p3-local"
  docker build --pull -f apps/Dockerfile -t "$IMAGE" .
else
  cd "$REPO"
  [[ -f dist/risu_v09_source/risu_fixverify.py ]] || {
    echo 'Reusable image mode requires a verified restored source tree' >&2;exit 2;
  }
fi
run_sandboxed() {
  docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --user 65534:65534 \
    --pids-limit 160 --memory 2g --cpus 2 \
    --tmpfs /tmp:rw,nosuid,nodev,size=512m,mode=1777 \
    --mount "type=bind,src=$TMP/results,dst=/results" "$@"
}
date +%s > "$TMP/results/begin_unix.txt"
run_sandboxed "$IMAGE"
run_sandboxed --entrypoint /opt/sdk/bin/python "$IMAGE" \
  -B /opt/risu/apps/replay_generated.py /results/repro_package/fixtures \
  --bridge /results/repro_package/consumer_bridge.py --expect broken
run_sandboxed --entrypoint /opt/sdk/bin/python "$IMAGE" \
  -B /opt/risu/apps/replay_generated.py /results/repro_package/fixtures \
  --bridge /results/repro_package/consumer_bridge_fixed.py --expect repaired
date +%s > "$TMP/results/end_unix.txt"
PYTHONPATH=dist/risu_v09_source python apps/audit_results.py "$TMP/results"
mkdir "$DEST"
cp -a "$TMP/results/." "$DEST/"
echo "RISU_P3_ONE_COMMAND_REPLAY_PASS $DEST"
