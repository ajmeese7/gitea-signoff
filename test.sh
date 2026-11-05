#!/usr/bin/env bash
# Pure-function tests. Network paths need a live Gitea and are covered manually.
set -euo pipefail
cd "$(dirname "$0")"
source ./gitea-signoff  # main() is guarded, so this only loads functions

fail=0
check() { # check <desc> <expected> <actual>
  if [ "$2" = "$3" ]; then echo "ok   - $1"; else
    echo "FAIL - $1: expected [$2] got [$3]"; fail=1; fi
}

check "default context"        "signoff"          "$(resolve_context)"
check "empty context"          "signoff"          "$(resolve_context "")"
check "named context"          "signoff/frontend" "$(resolve_context frontend)"

check "success symbol"         "$SYM_SUCCESS"     "$(state_symbol success)"
check "pending symbol"         "$SYM_PENDING"     "$(state_symbol pending)"
check "failure symbol"         "$SYM_FAILURE"     "$(state_symbol failure)"
check "unknown symbol"         "$SYM_FAILURE"     "$(state_symbol nonsense)"

for context in signoff signoff/web; do
  if is_signoff_context "$context"; then
    check "$context is signoff" yes yes
  else
    check "$context is signoff" yes no
  fi
done
for context in lint signoff-backup signoffXYZ; do
  if is_signoff_context "$context"; then
    check "$context is not signoff" no yes
  else
    check "$context is not signoff" no no
  fi
done

exit $fail
