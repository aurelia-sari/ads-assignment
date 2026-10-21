"""Live B1-B4 checks against ONE shared AI runtime and existing app proxies.

Uses only Python's standard library. Run on the deployment host after enabling
the four services. No local tests are replaced. Model requests run sequentially.
The workflow checks close their own test workflows by rejection, retaining the
server's append-only audit history; they never approve model output for release.
"""

import argparse
import html
import json
import math
import re
import sys
import time
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CheckFailed(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailed(message)


@dataclass
class Response:
    status: int
    text: str

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError as exc:
            raise CheckFailed("Expected JSON response") from exc


class Transport:
    def __init__(self, timeout=300):
        self.timeout = timeout

    def request(self, method, url, *, payload=None, form=None):
        headers = {"User-Agent": "NextStop-cloud-validation/1.0"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            with urlopen(Request(url, data=data, headers=headers, method=method),
                         timeout=self.timeout) as result:
                return Response(result.status, result.read().decode("utf-8"))
        except HTTPError as exc:
            return Response(exc.code, exc.read().decode("utf-8", errors="replace"))
        except (URLError, TimeoutError, OSError) as exc:
            raise CheckFailed(f"{method} {url}: {exc}") from exc


def ok(response, expected=(200,)):
    require(response.status in expected, f"HTTP {response.status}, expected {expected}")
    return response


def body(response, expected=(200,)):
    result = ok(response, expected).json()
    require(isinstance(result, dict), "Expected JSON object")
    require(not result.get("error") and not result.get("disabled"), "Error/disabled response")
    require(result.get("status") not in ("disabled", "unavailable", "failed"),
            "Service is disabled, unavailable or failed")
    return result


class Fragment(HTMLParser):
    """Collect rendered text and selected semantic elements, without a browser."""
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.nodes = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node = {"tag": tag, "attrs": attrs, "class": set(attrs.get("class", "").split()),
                "text": "", "own": "", "parent": self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data
        if self.stack:
            self.stack[-1]["own"] += data

    def texts(self, tag=None, classes=(), direct=False):
        return [node["own" if direct else "text"].strip() for node in self.nodes
                if (tag is None or node["tag"] == tag)
                and set(classes) <= node["class"]]

    def select(self, tag=None, classes=(), within=None):
        def descendant(node):
            parent = node["parent"]
            while parent is not None:
                if parent is within:
                    return True
                parent = parent["parent"]
            return False

        return [node for node in self.nodes
                if (tag is None or node["tag"] == tag)
                and set(classes) <= node["class"]
                and (within is None or descendant(node))]


def fragment(response):
    parsed = Fragment(ok(response).text)
    require(not parsed.texts(classes=("notice-error",)), "Application rendered an error/disabled notice")
    require(not parsed.texts(classes=("error",)), "Application rendered an error")
    return parsed


def validate_mcp(result, student):
    require(isinstance(result, dict), "Missing MCP result object")
    require(not result.get("isError"), "MCP refused the tool call")
    structured = result.get("structuredContent", result)
    require(isinstance(structured, dict), "Missing MCP structured result")
    require(structured.get("source") == f"student-{student}-db", "MCP returned the wrong data source")
    rows = structured.get("rows")
    require(isinstance(rows, list) and rows, "MCP tool returned no application data")
    require(structured.get("row_count") == len(rows), "MCP row count does not match data")
    return rows


def validate_numbered_citations(answer, numbers, label="RAG answer"):
    """Accept single or grouped numeric references, rejecting unknown numbers."""
    cited = set()
    malformed = []
    for group in re.findall(r"\[([^\[\]]+)\]", answer):
        if not re.match(r"\s*\d", group):
            continue
        if not re.fullmatch(r"\s*\d+(?:\s*,\s*\d+)*\s*", group):
            malformed.append(group)
            continue
        cited.update(int(value) for value in re.findall(r"\d+", group))
    excerpt = " ".join(answer.split())[:240]
    require(numbers and cited and cited <= numbers and not malformed,
            f"{label} does not reference retrieved citations: "
            f"allowed={sorted(numbers)}, cited={sorted(cited)}, "
            f"malformed={malformed}; answer={excerpt!r}")


def validate_rag(result, model):
    require(result.get("grounded") is True, "RAG did not produce a grounded answer")
    require(result.get("confidence") in ("low", "medium", "high"), "RAG has insufficient context")
    require(isinstance(result.get("answer"), str) and len(result["answer"].strip()) > 12,
            "RAG answer is missing/empty")
    require(result.get("model") == model, "RAG did not report the configured live model")
    citations = result.get("citations")
    require(isinstance(citations, list) and citations, "RAG answer has no citations")
    require(all(isinstance(c, dict) and c.get("source") and c.get("excerpt")
                and type(c.get("number")) is int and c["number"] > 0 for c in citations),
            "RAG citations have no retrieved source/context")
    validate_numbered_citations(result["answer"], {c["number"] for c in citations})


def validate_price_range_fact(answer):
    """Check one known corpus fact, beyond a model's own grounded=true claim."""
    text = answer.lower()
    require(re.search(r"\b(?:0|zero)\b", text) and re.search(r"\bfree\b", text),
            "RAG changed the documented fact: price_range 0 means free general entry")
    require(not re.search(r"\b(?:not|isn't|isn’t|doesn't|doesn’t)\b[^.]{0,40}\bfree\b", text),
            "RAG incorrectly says zero-priced entry is not free")
    require(not re.search(r"(?:a?\$|aud\s*)\s*[1-9]", text),
            "RAG invented a nonzero entry price")


def validate_workflow(workflow, student, model):
    require(workflow.get("feature") == f"student-{student}", "Workflow belongs to another feature")
    require(workflow.get("status") == "awaiting_human_review", "Workflow did not finish the agent sequence")
    require(not workflow.get("error"), "Workflow contains an error")
    plan = workflow.get("plan") or {}
    require(plan.get("source") == "model" and plan.get("model") == model,
            "Planner used a fallback or the wrong model")
    require(plan.get("steps") and plan.get("acceptance_criteria"), "Planner output is incomplete")
    attempts = workflow.get("attempts") or []
    require(bool(attempts), "No Worker/Reviewer attempt")
    worker = attempts[-1].get("worker") or {}
    review = attempts[-1].get("review") or {}
    require(worker.get("model") == model and bool(worker.get("response", "").strip()),
            "Worker did not return a live model answer")
    require(review.get("source") == "model" and review.get("model") == model,
            "Reviewer used a fallback or the wrong model")
    # A critical review is a completed Reviewer interaction: the human decides
    # what to release. Integration success must not require a favourable grade.
    require(review.get("verdict") in ("pass", "concerns", "fail"), "Reviewer returned no valid verdict")
    criteria = review.get("criteria")
    require(isinstance(criteria, list) and bool(criteria), "Reviewer did not evaluate any acceptance criteria")
    require(all(isinstance(item, dict) and isinstance(item.get("criterion"), str)
                and item["criterion"].strip() and type(item.get("met")) is bool
                for item in criteria), "Reviewer criteria need named checks and boolean evaluations")
    usable = {e["id"] for e in workflow.get("evidence", []) if isinstance(e, dict) and e.get("ok")}
    cited = set(re.findall(r"\[(E\d+)\]", worker["response"]))
    require(usable and cited and cited <= usable,
            "Worker answer is not traceable to usable evidence: "
            f"usable={sorted(usable)}, cited={sorted(cited)}; "
            f"answer={' '.join(worker['response'].split())[:240]!r}")


MCP = {
    1: ("list_trips", {}, "/ai/mcp", {"tool": "list_trips"}),
    2: ("search_places", {"category": "attraction"}, "/mcp/search-places", {"category": "attraction"}),
    3: ("find_travel_mates", {"status": "open"}, "/mcp/find-mates", {}),
    4: ("lookup_destination_guide", {"query": "Australia"}, "/mcp/destination-guide", {"query": "Australia"}),
    5: ("search_flights", {"destination": "Melbourne"}, "/mcp/call",
        {"tool": "search_flights", "arguments": {"destination": "Melbourne"}}),
}
RAG = {
    1: ("/ai/rag", "How are trips and itinerary days organised in NextStop?"),
    2: ("/rag/ask", "In NextStop, what does a place's price_range value of 0 mean? Answer in one short sentence with the passage citation."),
    3: ("/ai/ask-grounded", "How can travellers find travel mates and send a connection request?"),
    4: ("/rag/ask", "What information does a destination travel guide include?"),
    5: ("/ai/ask", "How should a traveller split the travel budget between flights and hotels?"),
}
AGENTS = {1: "/ai/agents", 2: "/agents/workflows", 3: "/ai/multi-agent"}
PENDING_WORKFLOW_STATUSES = {"queued", "planning", "gathering_evidence", "working", "reviewing"}


class CloudChecks:
    def __init__(self, transport, apps, ai, mcp, rag, agents, *, workflow_timeout=1200,
                 poll_interval=2, clock=time.monotonic, sleep=time.sleep):
        self.http = transport
        self.apps = apps
        self.ai, self.mcp, self.rag, self.agents = ai, mcp, rag, agents
        self.model = None
        self.marker = "cloud-validation-" + uuid.uuid4().hex
        self.workflow_timeout, self.poll_interval = workflow_timeout, poll_interval
        self.clock, self.sleep = clock, sleep

    def call(self, method, base, path, **kwargs):
        return self.http.request(method, base.rstrip("/") + path, **kwargs)

    def app(self, student, path, payload):
        encoding = "form" if student in (1, 3) else "payload"
        return self.call("POST", self.apps[student], path, **{encoding: payload})

    def readiness(self):
        for name, url in (("ai-mode", self.ai), ("mcp-server", self.mcp),
                          ("rag-server", self.rag), ("multi-agent-server", self.agents)):
            result = body(self.call("GET", url, "/health"))
            require(result.get("service") == name, f"Wrong service responding at {url}")
        result = body(self.call("GET", self.ai, "/model"))
        require(result.get("reachable") is True and result.get("model"), "Configured LLM is not reachable")
        self.model = result["model"]

    def b1(self):
        # This existing route only calls AI-Mode; it has no deterministic/RAG fallback.
        result = fragment(self.app(1, "/ai/chat", {
            "question": "Give one short tip for planning a travel itinerary."}))
        answers = result.texts(classes=("chat-msg", "bot"))
        require(answers and any(len(a.replace("NextStop AI", "").strip()) > 12 for a in answers),
                "Student 1 did not render a generated AI-Mode answer")

    def b2(self, student):
        tool, arguments, path, payload = MCP[student]
        direct = body(self.call("POST", self.mcp, "/mcp", payload={
            "jsonrpc": "2.0", "id": self.marker, "method": "tools/call",
            "params": {"name": tool, "arguments": arguments}}))
        direct_rows = validate_mcp(direct.get("result") or {}, student)
        response = self.app(student, path, payload)
        if student == 1:
            parsed = fragment(response)
            candidates = []
            for text in parsed.texts(tag="pre"):
                try:
                    candidates.append(json.loads(text))
                except ValueError:
                    pass
            require(bool(candidates), "Student 1 omitted its MCP structured result")
            rows = validate_mcp(candidates[-1], student)
            require(rows == direct_rows, "Student 1 MCP result differs from shared tool")
        elif student == 3:
            parsed = fragment(response)
            rendered = parsed.texts(classes=("trip-card__footer",))
            require(bool(rendered), "Student 3 did not render any MCP results")
            require(any(str(row["destination"]) in value for row in direct_rows for value in rendered),
                    "Student 3 results do not contain the shared tool's destinations")
        else:
            result = body(response)
            if student == 4:
                require(result.get("status") == "ok", "Student 4 MCP is not enabled")
            if student == 5:
                require(result.get("ok") is True, "Student 5 MCP call failed")
            rows = validate_mcp(result.get("result", result), student)
            require(rows == direct_rows, f"Student {student} MCP result differs from shared tool")

    def b3(self, student):
        path, question = RAG[student]
        search = body(self.call("POST", self.rag, "/search", payload={"question": question}))
        require(search.get("hits") and search.get("confidence") != "insufficient",
                "The deployed RAG knowledge index has no relevant context")
        response = self.app(student, path, {"question": question})
        if student in (1, 3):
            parsed = fragment(response)
            text = html.unescape(response.text)
            require("insufficient context" not in text.lower() and "Not enough context" not in text,
                    "Application returned an insufficient-context fallback")
            lists = parsed.texts(classes=("citation-list",))
            require(lists and any(hit["source"] in lists[0] for hit in search["hits"]),
                    "Application omitted retrieved source citations")
            if student == 1:
                bubbles = parsed.texts(classes=("bubble",), direct=True)
                answer = bubbles[-1] if bubbles else ""
            else:
                require("Grounded answer" in text, "Student 3 response is not grounded")
                paragraphs = parsed.texts(tag="p", direct=True)
                answer = paragraphs[1] if len(paragraphs) > 1 else ""
            require(len(answer.strip()) > 12, "Missing generated RAG answer")
            validate_numbered_citations(answer, {hit["number"] for hit in search["hits"]},
                                        "Rendered answer")
        else:
            result = body(response)
            validate_rag(result, self.model)
            if student == 2:
                validate_price_range_fact(result["answer"])

    def b4(self, student):
        path = AGENTS[student]
        tasks = {
            1: "Summarise one available trip and its destination using the supplied evidence. Cite its evidence ID.",
            2: "Recommend one Sydney attraction from the available places, with its evidence citation.",
            3: "Recommend one open travel companion trip and explain the match using the evidence.",
        }
        task = f"{tasks[student]} Validation reference {self.marker}."
        payload = {"task": task, "reviewer": self.marker}
        if student == 2:
            payload.update(city="Sydney", category="attraction")
        workflow_id = None
        failure = None
        deadline = self.clock() + self.workflow_timeout
        try:
            response = self.app(student, path, payload)
            # Capture an ID even in a failed model run, to close our own completed
            # workflows in finally. No workflow belonging to another run is touched.
            ids = re.findall(r"wf-[A-Za-z0-9-]{1,60}", response.text)
            workflow_id = ids[0] if ids else None
            ok(response, (200, 201, 202))
            require(workflow_id, "Application did not return a workflow ID")
            # The original HTML views do not include a feature field. Check
            # ownership in the saved JSON, while completion still has to pass
            # through this feature's application GET below.
            accepted = body(self.call("GET", self.agents, f"/workflows/{workflow_id}"))
            require(self.owns_workflow(accepted, student),
                    "Accepted workflow does not belong to this validation run and feature")
            self.wait_for_workflow(response, student, path, workflow_id, deadline)
            workflow = body(self.call("GET", self.agents, f"/workflows/{workflow_id}"))
            require(self.owns_workflow(workflow, student), "Workflow does not belong to this validation run")
            validate_workflow(workflow, student, self.model)
            verdict = workflow["attempts"][-1]["review"]["verdict"]
            print(f"  model Reviewer verdict: {verdict}; test output will be rejected after functional checks", flush=True)
            history = body(self.call("GET", self.agents, f"/workflows/{workflow_id}/history"))
            entries = history.get("history") or []
            sequence = [(e.get("actor"), e.get("event")) for e in entries]
            required = [("planner", "plan"), ("worker", "response"), ("reviewer", "review")]
            positions = [sequence.index(pair) if pair in sequence else -1 for pair in required]
            require(min(positions) >= 0 and positions == sorted(positions), "Agent audit sequence is incomplete")
        except Exception as exc:
            failure = exc
            raise
        finally:
            try:
                if workflow_id:
                    self.close_workflow(workflow_id, student, path)
                else:
                    self.recover_workflows(student, path)
            except (CheckFailed, KeyError, TypeError, ValueError) as exc:
                if failure is None:
                    raise
                # Preserve the original failed interaction as the result. A
                # cleanup failure must not turn a timeout into a passing check.
                print(f"  cleanup incomplete for {self.marker}: {exc}", flush=True)

    def application_workflow(self, response, student, workflow_id):
        """Validate status through the same application proxy used to start it."""
        ok(response, (200, 201, 202))
        if student == 2:
            workflow = body(response, (200, 201, 202))
            require(workflow.get("id") == workflow_id, "Application returned another workflow ID")
            require(self.owns_workflow(workflow, student), "Application returned another run or feature")
            status = workflow.get("status")
        else:
            parsed = fragment(Response(200, response.text))
            cards = (parsed.select("article", classes=("agent-run",)) if student == 1
                     else parsed.select("div", classes=("card", "agent-card")))
            require(len(cards) == 1, "Application did not render one workflow card")
            card = cards[0]
            if student == 1:
                headers = parsed.select("header", classes=("agent-run__head",), within=card)
                require(len(headers) == 1, "Application omitted the workflow header")
                header = headers[0]
                tasks = parsed.select("strong", within=header)
                require(len(tasks) == 1, "Application omitted the workflow task")
                task = tasks[0]["text"]
            else:
                require(card["attrs"].get("id") == workflow_id,
                        "Application returned another workflow ID")
                paragraphs = [node for node in parsed.select("p", within=card)
                              if node["parent"] is card]
                require(bool(paragraphs), "Application omitted the workflow header")
                header = paragraphs[0]
                tasks = [node for node in paragraphs if "muted" in node["class"]
                         and node["text"].startswith("Task: ")]
                require(len(tasks) == 1, "Application omitted the workflow task")
                task = tasks[0]["text"][len("Task: "):]
            ids = parsed.select("code", within=header)
            require(len(ids) == 1 and ids[0]["text"].strip() == workflow_id,
                    "Application returned another workflow ID")
            require(f"Validation reference {self.marker}." in task,
                    "Application returned another validation run")
            pills = parsed.select("span", classes=("pill",), within=header)
            require(len(pills) == 1, "Application omitted one workflow status")
            pill = pills[0]
            label = pill["text"].strip()
            if student == 1:
                labels = {state.replace("_", " "): state for state in
                          PENDING_WORKFLOW_STATUSES | {"approved", "partially_accepted", "rejected", "failed"}}
                labels["awaiting your review"] = "awaiting_human_review"
                status = labels.get(label)
            else:
                classes = [css[5:] for css in pill["class"] if css.startswith("pill-")]
                require(len(classes) == 1 and classes[0] == label,
                        "Application rendered an inconsistent workflow status")
                status = classes[0]
        require(status in PENDING_WORKFLOW_STATUSES | {"awaiting_human_review", "rejected"},
                f"Application workflow is failed or unexpected: {status}")
        return status

    def wait_for_workflow(self, response, student, path, workflow_id, deadline):
        """Allow slow CPU generation without bypassing a broken application GET."""
        last_status = None
        polled = False
        started = deadline - self.workflow_timeout
        while True:
            status = self.application_workflow(response, student, workflow_id)
            require(self.clock() < deadline,
                    f"Workflow exceeded {self.workflow_timeout:g}s deadline; last application status={status}")
            if status == "awaiting_human_review":
                if polled:
                    return
                # Even synchronous starts must expose their result through the
                # application's existing read route, not only the shared API.
                response = self.call("GET", self.apps[student], path + f"/{workflow_id}")
                polled = True
                continue
            require(status in PENDING_WORKFLOW_STATUSES,
                    f"Workflow ended before its agent output could be validated: {status}")
            if status != last_status:
                print(f"  waiting {workflow_id}: application status={status}; "
                      f"elapsed={self.clock() - started:.0f}s", flush=True)
                last_status = status
            remaining = deadline - self.clock()
            self.sleep(min(self.poll_interval, remaining))
            require(self.clock() < deadline,
                    f"Workflow exceeded {self.workflow_timeout:g}s deadline; last application status={status}")
            response = self.call("GET", self.apps[student], path + f"/{workflow_id}")
            polled = True

    def owns_workflow(self, workflow, student):
        return (workflow.get("feature") == f"student-{student}"
                and f"Validation reference {self.marker}." in workflow.get("task", ""))

    def recover_workflows(self, student, path):
        # An HTTP timeout does not cancel the shared server's model request.
        # Query once, using our unique marker and feature, without waiting on or
        # mutating unrelated users' work. Still-running records are reported.
        result = body(self.call("GET", self.agents, f"/workflows?feature=student-{student}&limit=200"))
        rows = result.get("workflows")
        require(isinstance(rows, list), "Could not recover workflow IDs after the failed request")
        own = [row for row in rows if isinstance(row, dict) and self.owns_workflow(row, student)]
        for row in own:
            workflow_id = row.get("id", "")
            require(re.fullmatch(r"wf-[A-Za-z0-9-]{1,60}", workflow_id), "Invalid recovered workflow ID")
            self.close_workflow(workflow_id, student, path)
        if not own:
            print(f"  no completed/visible workflow found for {self.marker}; a timed-out request may still finish later",
                  flush=True)

    def close_workflow(self, workflow_id, student, path):
        # Failed workflows intentionally carry an error field. They are terminal
        # and must remain in the audit; only pending human review can be rejected.
        current = ok(self.call("GET", self.agents, f"/workflows/{workflow_id}")).json()
        require(isinstance(current, dict), "Expected workflow JSON object")
        require(self.owns_workflow(current, student), "Refusing to change another run's workflow")
        if current.get("status") != "awaiting_human_review":
            print(f"  retained {workflow_id}: status={current.get('status')}; audit is append-only", flush=True)
            return
        note = "Automated cloud validation finished; test output must not be released."
        payload = {"decision": "reject", "reviewer": self.marker, "comment": note}
        if student == 2:
            payload.update(decision="Reject", notes=note)
        decided = self.app(student, path + f"/{workflow_id}/decision", payload)
        require(self.application_workflow(decided, student, workflow_id) == "rejected",
                "Application did not confirm rejection of the test workflow")
        result = body(self.call("GET", self.agents, f"/workflows/{workflow_id}"))
        require(result.get("status") == "rejected", "Test workflow was not closed by rejection")
        require(not result.get("final_response"), "Test output was unexpectedly released")
        print(f"  closed {workflow_id}; server audit retained", flush=True)


def assignments(values):
    result = {}
    for value in values:
        try:
            student, url = value.split("=", 1)
            number = int(student)
            if number not in range(1, 6) or not url.startswith(("http://", "https://")):
                raise ValueError
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Use N=http(s)://host:port, with N from 1 to 5") from exc
        result[number] = url.rstrip("/")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--workflow-timeout", type=float, default=1200,
                        help="Total B4 generation deadline, including application status polling")
    parser.add_argument("--poll-interval", type=float, default=2,
                        help="Seconds between B4 application status requests")
    parser.add_argument("--frontend-url", action="append", default=[], metavar="N=URL",
                        help="Frontend root; /api/student-N is appended (default http://HOST:808N)")
    parser.add_argument("--api-url", action="append", default=[], metavar="N=URL",
                        help="Override complete application API base, including any proxy prefix")
    for name in ("ai", "mcp", "rag", "agents"):
        parser.add_argument(f"--{name}-url")
    args = parser.parse_args(argv)
    try:
        frontends = {n: f"http://{args.host}:{8080+n}" for n in range(1, 6)}
        frontends.update(assignments(args.frontend_url))
        apps = {n: url + f"/api/student-{n}" for n, url in frontends.items()}
        apps.update(assignments(args.api_url))
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    for option in ("timeout", "workflow_timeout", "poll_interval"):
        if not math.isfinite(getattr(args, option)) or getattr(args, option) <= 0:
            parser.error(f"--{option.replace('_', '-')} must be finite and positive")
    shared = [getattr(args, name + "_url") or f"http://{args.host}:{port}"
              for name, port in (("ai", 5300), ("mcp", 5400), ("rag", 5500), ("agents", 5600))]
    checks = CloudChecks(Transport(args.timeout), apps, *shared,
                         workflow_timeout=args.workflow_timeout, poll_interval=args.poll_interval)
    try:
        checks.readiness()
    except (CheckFailed, KeyError, TypeError) as exc:
        print(f"FAIL shared readiness: {exc}", flush=True)
        return 1
    print(f"PASS shared runtime and live model: {checks.model}", flush=True)
    cases = [("B1 student-1 AI-Mode application interaction", checks.b1)]
    cases += [(f"B2 student-{n} MCP application interaction", lambda n=n: checks.b2(n)) for n in range(1, 6)]
    cases += [(f"B3 student-{n} grounded RAG application interaction", lambda n=n: checks.b3(n)) for n in range(1, 6)]
    cases += [(f"B4 student-{n} Planner/Worker/Reviewer application interaction", lambda n=n: checks.b4(n)) for n in (1, 2, 3)]
    failed = 0
    for label, operation in cases:
        print(f"RUN {label}", flush=True)
        try:
            operation()
        except (CheckFailed, KeyError, TypeError, ValueError) as exc:
            failed += 1
            print(f"FAIL {label}: {exc}", flush=True)
        else:
            print(f"PASS {label}", flush=True)
    print("Coverage: B1 direct AI-Mode app=student-1; B2/B3 apps=student-1..5; B4 apps=student-1..3.")
    print("B4 student-4/5: no existing application routes; not claimed as validated. No frontend files changed.")
    print(f"{len(cases)-failed}/{len(cases)} supported cloud interaction checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
