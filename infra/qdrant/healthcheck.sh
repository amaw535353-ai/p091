#!/usr/bin/env bash
set -euo pipefail
exec 3<>/dev/tcp/127.0.0.1/6333
printf 'GET /readyz HTTP/1.0\r\nHost: localhost\r\napi-key: %s\r\n\r\n' "$QDRANT__SERVICE__API_KEY" >&3
IFS= read -r status <&3
[[ "$status" == *' 200 '* ]]
