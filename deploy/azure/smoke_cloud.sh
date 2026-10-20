#!/usr/bin/env bash
# Post-deploy validation of the cloud deployment.
set -uo pipefail
: "${VM_HOST:?set VM_HOST}"
SSH_KEY=${SSH_KEY:-$HOME/.ssh/nextstop_deploy}
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new azureuser@$VM_HOST"
fail=0

check() {
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$2" || true)
  if [ "$code" = "200" ]; then echo "PASS  $1  ($2)"; else echo "FAIL  $1  ($2) -> HTTP $code"; fail=1; fi
}

echo "== 1. Public frontends =="
check "home page"          "http://$VM_HOST/"
check "home page (8080)"   "http://$VM_HOST:8080/"
for n in 1 2 3 4 5; do check "student-$n frontend" "http://$VM_HOST:808$n/"; done

echo "== 2. AI services disabled by default =="
for n in 1 2 3 4 5; do
  vals=$($SSH "docker exec student-$n-api printenv AI_MODE_ENABLED MCP_ENABLED RAG_ENABLED MULTI_AGENT_ENABLED" | tr '\n' ' ')
  if [ "$vals" = "false false false false " ]; then echo "PASS  student-$n-api flags: $vals"; else echo "FAIL  student-$n-api flags: $vals"; fail=1; fi
done

echo "== 3. Backend CRUD smoke tests (run on the VM against each API) =="
for n in 1 2 3 4 5; do
  echo "-- student $n --"
  if $SSH "cd ~/nextstop && CI=true python3 scripts/smoke_test.py $n"; then
    echo "PASS  student-$n smoke test"
  else
    echo "FAIL  student-$n smoke test"; fail=1
  fi
done

[ "$fail" = "0" ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $fail
