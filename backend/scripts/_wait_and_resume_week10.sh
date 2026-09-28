#!/bin/bash
# Polls the Groq daily-quota wall every 10 minutes with a minimal, near-zero-cost
# check call, then runs the Week 10 race in --resume mode the moment quota is
# available again -- reusing the 7 already-clean checkpointed cases and only
# spending quota on the 3 that never got a real attempt (r08-r10) plus the
# failure demo, then regenerating race_table.md/handoffs.log/verdict.md.
set -u
cd "$(dirname "$0")/.."

check() {
  python -c "
from dotenv import load_dotenv
load_dotenv()
from agent.llm import tool_llm
from langchain_core.messages import SystemMessage, HumanMessage
try:
    tool_llm().invoke([SystemMessage(content='t'), HumanMessage(content='hi')])
    print('OK')
except Exception as e:
    print('BLOCKED:', str(e)[:120])
" 2>&1
}

attempt=0
while true; do
  attempt=$((attempt + 1))
  out=$(check)
  echo "[check $attempt] $out"
  case "$out" in
    OK*) break ;;
  esac
  sleep 600
done

echo "=== quota available -- resuming Week 10 race ==="
python scripts/race_week10.py --resume --pace 2
echo "=== resume run finished, exit code $? ==="
