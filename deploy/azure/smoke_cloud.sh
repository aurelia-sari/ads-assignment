#!/usr/bin/env bash
# Validate the selected cloud runtime; local and baseline tests stay unchanged.
set -uo pipefail
: "${VM_HOST:?set VM_HOST}"
ENABLE_CLOUD_AI=${ENABLE_CLOUD_AI:-false}
case "$ENABLE_CLOUD_AI" in true|false) ;; *) echo 'ENABLE_CLOUD_AI must be true or false' >&2; exit 2 ;; esac
[[ "$VM_HOST" =~ ^[[:alnum:]][[:alnum:].-]*$ ]] || exit 2
SSH_KEY=${SSH_KEY:-$HOME/.ssh/nextstop_deploy}
SSH=(ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "azureuser@$VM_HOST")
fail=0

check() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$2" || true)
  if [ "$code" = 200 ]; then echo "PASS  $1"; else echo "FAIL  $1 -> HTTP $code"; fail=1; fi
}

echo '== Public frontends =='
check 'home page' "http://$VM_HOST/"
check 'home page (8080)' "http://$VM_HOST:8080/"
for n in 1 2 3 4 5; do check "student-$n frontend" "http://$VM_HOST:808$n/"; done

echo "== Application AI flags (expected: $ENABLE_CLOUD_AI) =="
expected="$ENABLE_CLOUD_AI $ENABLE_CLOUD_AI $ENABLE_CLOUD_AI $ENABLE_CLOUD_AI "
for n in 1 2 3 4 5; do
  vals=$("${SSH[@]}" "docker exec student-$n-api printenv AI_MODE_ENABLED MCP_ENABLED RAG_ENABLED MULTI_AGENT_ENABLED" | tr '\n' ' ')
  if [ "$vals" = "$expected" ]; then
    echo "PASS  student-$n-api flags"
  else
    echo "FAIL  student-$n-api flags: $vals"; fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  if [ "$ENABLE_CLOUD_AI" = true ]; then
    echo '== One shared cloud AI runtime: B1-B4 application interactions =='
    "${SSH[@]}" 'cd ~/nextstop && python3 tests/cloud/check_cloud_ai.py --host 127.0.0.1 --timeout 300 --workflow-timeout 1200' || fail=1
  else
    echo '== Existing baseline backend CRUD tests =='
    for n in 1 2 3 4 5; do
      if "${SSH[@]}" "cd ~/nextstop && CI=true python3 scripts/smoke_test.py $n"; then
        echo "PASS  student-$n baseline smoke test"
      else
        echo "FAIL  student-$n baseline smoke test"; fail=1
      fi
    done
  fi
fi

if [ "$fail" -eq 0 ]; then echo 'ALL CHECKS PASSED'; else echo 'SOME CHECKS FAILED'; fi
exit "$fail"
