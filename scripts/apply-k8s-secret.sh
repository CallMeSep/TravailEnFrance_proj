#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"
NAMESPACE="${2:-travail-en-france}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

python3 - "$ENV_FILE" "$NAMESPACE" <<'PY'
from pathlib import Path
import subprocess
import sys

env_file = Path(sys.argv[1])
namespace = sys.argv[2]

vals = {}
for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = line.strip().rstrip("\r")
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    vals[key.strip()] = value.strip().rstrip("\r")

for req in ("FT_CLIENT_ID", "FT_CLIENT_SECRET", "FT_SCOPE"):
    if not vals.get(req):
        raise SystemExit(f"{req} is required in {env_file}")

cmd = [
    "kubectl",
    "create",
    "secret",
    "generic",
    "app-secret",
    "-n",
    namespace,
    "--from-literal=POSTGRES_DB=jobsdb",
    "--from-literal=POSTGRES_USER=jobsuser",
    "--from-literal=POSTGRES_PASSWORD=change-me",
    "--from-literal=DATABASE_URL=postgresql://jobsuser:change-me@postgres:5432/jobsdb",
    "--from-literal=PASSWORD_SALT=change-this-salt",
    "--from-literal=FLASK_SECRET_KEY=change-this-secret",
    f"--from-literal=FT_CLIENT_ID={vals['FT_CLIENT_ID']}",
    f"--from-literal=FT_CLIENT_SECRET={vals['FT_CLIENT_SECRET']}",
    f"--from-literal=FT_SCOPE={vals['FT_SCOPE']}",
    "--dry-run=client",
    "-o",
    "yaml",
]

manifest = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
subprocess.run(["kubectl", "apply", "-f", "-"], input=manifest, check=True, text=True)
print(f"app-secret applied in namespace '{namespace}'.")
PY
