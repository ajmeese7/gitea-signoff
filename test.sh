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

is_signoff_context signoff          && check "signoff is signoff"      yes yes || check "signoff is signoff" yes no
is_signoff_context signoff/web      && check "signoff/web is signoff"  yes yes || check "signoff/web is signoff" yes no
is_signoff_context lint             && check "lint is not signoff"     yes no  || check "lint is not signoff" yes yes

exit $fail
