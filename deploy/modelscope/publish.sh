#!/usr/bin/env bash
# Publish the prepared ModelScope Docker Studio bundle.
#
# Prerequisites:
#   pip install modelscope-hub
#   workspace/.secrets/modelscope_token contains a ModelScope access token
#   the account has completed real-name verification (required for Docker Studios)
#
# Usage:
#   deploy/modelscope/publish.sh <owner>/<studio-name>
#
# Optional environment:
#   BUNDLE=/path/to/bundle              default: <workspace>/modelscope-studio/memlab
#   MODELSCOPE_TOKEN_FILE=/path/to/token
#   MODELSCOPE=...                      default: modelscope on PATH
#   GIT_USER_NAME / GIT_USER_EMAIL      commit identity
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE="$(cd "$ROOT/.." && pwd)"
STUDIO_ID="${1:?usage: publish.sh <owner>/<studio-name>}"
TOKEN_FILE="${MODELSCOPE_TOKEN_FILE:-$WORKSPACE/.secrets/modelscope_token}"
BUNDLE="${BUNDLE:-$WORKSPACE/modelscope-studio/memlab}"
MODELSCOPE="${MODELSCOPE:-modelscope}"
GIT_USER_NAME="${GIT_USER_NAME:-JOY1211}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-annasha_joy@qq.com}"

if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "missing token file: $TOKEN_FILE" >&2
  echo "write one line with a ModelScope access token, then rerun." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
if [[ -z "$TOKEN" ]]; then
  echo "token file is empty: $TOKEN_FILE" >&2
  exit 1
fi
if [[ ! -f "$BUNDLE/Dockerfile" ]]; then
  echo "missing bundle: $BUNDLE (run deploy/modelscope/build_bundle.py)" >&2
  exit 1
fi

export MODELSCOPE_API_TOKEN="$TOKEN"

if ! "$MODELSCOPE" info --repo-type studio "$STUDIO_ID" >/dev/null 2>&1; then
  echo "creating Docker Studio $STUDIO_ID ..."
  "$MODELSCOPE" create \
    --repo-type studio \
    --sdk-type docker \
    --visibility public \
    --license "Apache License 2.0" \
    --chinese-name "动态记忆工作台" \
    --description "Dynamic Memory Workbench: memory browser, state/evidence inspection, and B0/R0 online-offline evaluation." \
    --exist-ok \
    "$STUDIO_ID"
fi

WORK="$(mktemp -d /tmp/memlab-studio.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
REPO_DIR="$WORK/studio"
clone_url="https://oauth2:${TOKEN}@www.modelscope.cn/studios/${STUDIO_ID}.git"
GIT_TERMINAL_PROMPT=0 git clone "$clone_url" "$REPO_DIR"

# Replace code but keep the repository metadata (.git, .gitattributes).
# The bundle must not contain its own .git, or it would overwrite the clone's
# remote and make `git push` fail with "origin does not appear to be a repo".
find "$REPO_DIR" -mindepth 1 -maxdepth 1 ! -name .git ! -name .gitattributes -exec rm -rf {} +
( cd "$BUNDLE" && tar --exclude=.git --exclude=__pycache__ --exclude='*.pyc' -cf - . ) | ( cd "$REPO_DIR" && tar -xf - )

cd "$REPO_DIR"
git add -A
if ! git diff --cached --quiet; then
  git -c "user.name=$GIT_USER_NAME" -c "user.email=$GIT_USER_EMAIL" \
    commit -m "deploy dynamic memory workbench web"
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:master
else
  echo "no bundle changes to commit"
fi

echo "triggering deploy for $STUDIO_ID ..."
"$MODELSCOPE" deploy --repo-type studio "$STUDIO_ID"
echo "studio: https://www.modelscope.cn/studios/$STUDIO_ID"
echo "check logs: $MODELSCOPE studio logs $STUDIO_ID"
