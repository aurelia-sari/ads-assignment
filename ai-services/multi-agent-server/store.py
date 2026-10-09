"""Workflow persistence and the coordination/audit log.

Two records are kept, on purpose:

  workflows/<id>.json   the current state of one workflow - plan, evidence,
                        every Worker attempt, every review, every human
                        decision. Rewritten as the workflow advances.
  audit.jsonl           an append-only log of every step any agent or human
                        took, across all workflows. Never rewritten.

The workflow file answers "where is this workflow now". The audit log answers
"who did what, in what order", and because it is append-only it still holds
the full story after a workflow is corrected and re-run. That log is the
coordination/audit evidence the Release 2 report asks for.

Plain files rather than a database: the server is a single local process, the
volumes are tiny, and a reader can open the evidence in any editor.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(
    os.getenv(
        "MULTI_AGENT_DATA_DIR",
        Path(__file__).resolve().parent.parent / ".runtime" / "multi-agent",
    )
)
WORKFLOW_DIR = DATA_DIR / "workflows"
AUDIT_LOG = DATA_DIR / "audit.jsonl"

_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id():
    return "wf-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _workflow_path(workflow_id):
    # Ids are generated here, but they also arrive in URLs. Refuse anything
    # that is not one of ours rather than let it reach the filesystem.
    if not workflow_id.startswith("wf-") or not all(
        ch.isalnum() or ch == "-" for ch in workflow_id
    ):
        raise KeyError(workflow_id)
    return WORKFLOW_DIR / f"{workflow_id}.json"


def save(workflow):
    workflow["updated_at"] = now()
    with _lock:
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        path = _workflow_path(workflow["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
        tmp.replace(path)
    return workflow


def load(workflow_id):
    path = _workflow_path(workflow_id)
    if not path.exists():
        raise KeyError(workflow_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_workflows(feature=None, status=None, limit=50):
    if not WORKFLOW_DIR.exists():
        return []
    rows = []
    for path in sorted(WORKFLOW_DIR.glob("wf-*.json"), reverse=True):
        workflow = json.loads(path.read_text(encoding="utf-8"))
        if feature and workflow["feature"] != feature:
            continue
        if status and workflow["status"] != status:
            continue
        rows.append(workflow)
        if len(rows) >= limit:
            break
    return rows


def audit(workflow_id, actor, event, detail=None):
    """Append one step to the audit log and return it."""
    entry = {
        "ts": now(),
        "workflow_id": workflow_id,
        "actor": actor,
        "event": event,
        "detail": detail or {},
    }
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    return entry


def history(workflow_id):
    """Every audit entry for one workflow, oldest first."""
    if not AUDIT_LOG.exists():
        return []
    entries = []
    with AUDIT_LOG.open(encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            if entry["workflow_id"] == workflow_id:
                entries.append(entry)
    return entries
