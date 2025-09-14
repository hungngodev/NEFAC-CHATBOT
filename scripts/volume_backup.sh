#!/usr/bin/env bash
set -euo pipefail

# Simple local backup/restore helper for Docker volumes defined in
# backend/docker-compose.databases.yml (Elasticsearch, Qdrant, Neo4j).
#
# Usage:
#   # Backup all three volumes to tar.zst files in current directory
#   scripts/volume_backup.sh backup all
#
#   # Backup a specific service (elasticsearch|qdrant|neo4j)
#   scripts/volume_backup.sh backup elasticsearch
#
#   # Restore a tar.zst into a volume (creates volume if missing)
#   scripts/volume_backup.sh restore esdata ./backend_esdata.tar.zst
#
# Requirements:
#   - docker / docker compose
#   - zstd installed on host (for .tar.zst). If not available, script falls back to .tar.gz
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/backend/docker-compose.databases.yml"

# Map service -> volume and optional chown after restore
declare -A SERVICE_TO_VOLUME=(
  [elasticsearch]="esdata"
  [qdrant]="qdrant-data"
  [neo4j]="neo4j-data"
)

declare -A RESTORE_CHOWN=(
  # ES runs as uid:gid 1000:1000 by default
  [esdata]="1000:1000"
)

_have_zstd() { command -v zstd >/dev/null 2>&1; }

_backup_one() {
  local service="$1"; shift
  local volume="${SERVICE_TO_VOLUME[$service]:-}"
  if [[ -z "$volume" ]]; then
    echo "Unknown service: $service" >&2; exit 1
  fi

  echo "[INFO] Stopping $service …"
  docker compose -f "$COMPOSE_FILE" stop "$service"

  if _have_zstd; then
    local out="${PWD}/backend_${volume}.tar.zst"
    echo "[INFO] Backing up volume $volume to $out (zstd)…"
    docker run --rm -v "$volume":/data busybox sh -c 'cd /data && tar cf - .' | zstd -19 -o "$out"
  else
    local out="${PWD}/backend_${volume}.tar.gz"
    echo "[INFO] Backing up volume $volume to $out (gzip)…"
    docker run --rm -v "$volume":/data busybox sh -c 'cd /data && tar czf - .' > "$out"
  fi

  echo "[INFO] Starting $service …"
  docker compose -f "$COMPOSE_FILE" start "$service"
}

_restore_one() {
  local volume="$1"; shift
  local archive="$1"; shift
  if [[ ! -f "$archive" ]]; then
    echo "Archive not found: $archive" >&2; exit 1
  fi

  # Create target volume if missing
  if ! docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "[INFO] Creating volume $volume …"
    docker volume create "$volume" >/dev/null
  fi

  echo "[INFO] Restoring $archive into volume $volume …"
  if [[ "$archive" == *.zst ]]; then
    zstd -d -c "$archive" | docker run --rm -i -v "$volume":/data busybox sh -c 'cd /data && tar xf -'
  else
    cat "$archive" | docker run --rm -i -v "$volume":/data busybox sh -c 'cd /data && tar xzf -'
  fi

  # Fix ownership for services that need specific uids
  if [[ -n "${RESTORE_CHOWN[$volume]:-}" ]]; then
    echo "[INFO] Fixing ownership on $volume to ${RESTORE_CHOWN[$volume]} …"
    docker run --rm -v "$volume":/data busybox sh -c "chown -R ${RESTORE_CHOWN[$volume]} /data"
  fi

  echo "[INFO] Restore complete for $volume"
}

_usage() {
  cat <<EOF
Usage:
  $0 backup all
  $0 backup (elasticsearch|qdrant|neo4j)
  $0 restore <volume-name> <archive.tar.zst|.tar.gz>

Examples:
  $0 backup all
  $0 backup elasticsearch
  $0 restore esdata ./backend_esdata.tar.zst
EOF
}

main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    backup)
      local target="${1:-all}"; shift || true
      case "$target" in
        all)
          _backup_one elasticsearch
          _backup_one qdrant
          _backup_one neo4j
          ;;
        elasticsearch|qdrant|neo4j)
          _backup_one "$target"
          ;;
        *)
          echo "Unknown backup target: $target" >&2
          _usage; exit 1
          ;;
      esac
      ;;
    restore)
      local volume="${1:-}"; shift || true
      local archive="${1:-}"; shift || true
      if [[ -z "$volume" || -z "$archive" ]]; then
        _usage; exit 1
      fi
      _restore_one "$volume" "$archive"
      ;;
    *)
      _usage; exit 1
      ;;
  esac
}

main "$@"
