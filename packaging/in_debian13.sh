#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
if [[ ! -f "$project_dir/build/debian13/rootfs/etc/debian_version" ]]; then
  echo "Falta preparar el rootfs Debian 13 en build/debian13/rootfs." >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then
  echo "Uso: bash packaging/in_debian13.sh COMANDO [ARGUMENTOS...]" >&2
  exit 1
fi
mkdir -p "$project_dir/dist" "$project_dir/build/debian13/tools"
exec bwrap --unshare-user --uid 0 --gid 0 --unshare-pid --die-with-parent --clearenv \
  --setenv PATH /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --setenv LC_ALL C.UTF-8 --setenv DEBIAN_FRONTEND noninteractive \
  --bind "$project_dir/build/debian13/rootfs" / --proc /proc --dev /dev \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --dir /work --ro-bind "$project_dir/src" /work/src \
  --ro-bind "$project_dir/packaging" /work/packaging \
  --ro-bind "$project_dir/docs/releases" /work/docs/releases \
  --ro-bind "$project_dir/LICENSE" /work/LICENSE \
  --ro-bind "$project_dir/pyproject.toml" /work/pyproject.toml \
  --ro-bind "$project_dir/tests" /work/tests \
  --bind "$project_dir/dist" /work/dist \
  --ro-bind "$project_dir/build/debian13/tools" /tools \
  --chdir /work "$@"
