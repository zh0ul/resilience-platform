#!/usr/bin/env bash
# Mount NFS/SMB fixture paths when running the protocols profile, then exec the test command.
set -euo pipefail

NFS_MOUNT="${RESILIENCE_NFS_MOUNT:-/mnt/qumulo-nfs}"
SMB_MOUNT="${RESILIENCE_SMB_MOUNT:-/mnt/qumulo-smb}"

cleanup() {
  if mountpoint -q "${SMB_MOUNT}" 2>/dev/null; then
    umount "${SMB_MOUNT}" || true
  fi
  if mountpoint -q "${NFS_MOUNT}" 2>/dev/null; then
    umount "${NFS_MOUNT}" || true
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "${NFS_MOUNT}" "${SMB_MOUNT}"

if [[ "${RESILIENCE_ENABLE_LIVE_TESTS:-false}" == "true" ]]; then
  if [[ -n "${QUMULO_NFS_EXPORT:-}" ]]; then
    echo "Mounting NFS export ${QUMULO_NFS_EXPORT} -> ${NFS_MOUNT}"
    mount -t nfs -o vers=3,nolock "${QUMULO_NFS_EXPORT}" "${NFS_MOUNT}"
  fi

  if [[ -n "${QUMULO_SMB_SERVER:-}" && -n "${QUMULO_SMB_SHARE:-}" ]]; then
    SMB_CRED="/tmp/smb-credentials"
    cat > "${SMB_CRED}" <<EOF
username=${QUMULO_SMB_USER}
password=${QUMULO_SMB_PASSWORD}
domain=${QUMULO_SMB_DOMAIN:-}
EOF
    chmod 600 "${SMB_CRED}"
    echo "Mounting SMB share //${QUMULO_SMB_SERVER}/${QUMULO_SMB_SHARE} -> ${SMB_MOUNT}"
    mount -t cifs "//${QUMULO_SMB_SERVER}/${QUMULO_SMB_SHARE}" "${SMB_MOUNT}" \
      -o "credentials=${SMB_CRED},vers=3.0,uid=0,gid=0"
  fi
fi

exec "$@"
