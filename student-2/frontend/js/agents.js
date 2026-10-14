/* Release 2: all network calls go through student-2-api. Model text stays text. */
window.initialiseAgents = function () {
    const panel = document.getElementById("panel-agents");
    if (!panel?.querySelector("#agents-run-form") || panel.dataset.initialised) return;
    panel.dataset.initialised = "true";
    const el = id => document.getElementById(`agents-${id}`);
    let current = null;
    let busy = false;
    let poll = null;
    let recentRevision = 0;
    const terminal = new Set(["awaiting_human_review", "approved", "partially_accepted", "rejected", "failed"]);
    const labels = {approve: "Accept", partial: "Partially Accept", reject: "Reject"};
    const finalStatuses = {approve: "approved", partial: "partially_accepted", reject: "rejected"};

    // Use only a verified session; never trust a cached browser identity alone.
    let reviewerEdited = false;
    el("reviewer-name").addEventListener("input", () => { reviewerEdited = true; });
    async function fillReviewerName() {
        let user = null;
        try { user = await window.NextStopSession?.verifySession(); }
        catch (_) { /* Session lookup failure leaves manual entry available. */ }
        const name = typeof user?.name === "string" ? user.name.trim() : "";
        if (name && name.length <= 100 && !reviewerEdited && !el("reviewer-name").value.trim()) {
            el("reviewer-name").value = name;
            el("reviewer-hint").textContent = "Filled from your signed-in session. You can edit this name.";
        } else {
            el("reviewer-hint").textContent = "Enter your name to record who reviewed this result.";
        }
    }

    async function api(path, body) {
        let response;
        try {
            response = await fetch(`/api/student-2/agents${path}`, body === undefined ? {} : {
                method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
            });
        } catch (_) { throw new Error("The Student 2 service is unavailable. No save has been confirmed."); }
        let data;
        try { data = await response.json(); }
        catch (_) { throw new Error("The service returned an invalid response."); }
        if (!response.ok) {
            const error = new Error(data.error || "The request failed.");
            error.workflow = data.workflow;
            throw error;
        }
        return data;
    }
    function message(id, text, error = false) {
        el(id).textContent = text;
        el(id).classList.toggle("integration-error", error);
    }
    function controls() {
        el("run-form").querySelectorAll("input, textarea, select, button").forEach(c => c.disabled = busy);
        ["resume", "resume-id", "recent-refresh"].forEach(id => el(id).disabled = busy);
        el("recent").querySelectorAll("button").forEach(c => c.disabled = busy);
        el("refresh").disabled = busy || !current;
        el("review-fields").disabled = busy || current?.status !== "awaiting_human_review";
        const accept = panel.querySelector('[name="agent-decision"][value="Accept"]');
        accept.disabled = !current?.student2_validation?.can_accept;
        if (accept.disabled && accept.checked && current?.status === "awaiting_human_review") {
            panel.querySelector('[name="agent-decision"][value="Reject"]').checked = true; updateNotes();
        }
        panel.setAttribute("aria-busy", String(busy));
    }
    function paragraph(target, text) {
        const p = document.createElement("p"); p.textContent = text; target.append(p);
    }
    function list(target, title, items) {
        paragraph(target, title);
        const ul = document.createElement("ul");
        (items || []).forEach(item => { const li = document.createElement("li"); li.textContent = item; ul.append(li); });
        target.append(ul);
    }
    function render(w) {
        current = w;
        el("result-card").hidden = false; el("empty").hidden = true;
        el("id").textContent = w.id;
        el("status").textContent = w.status.replaceAll("_", " ");
        const {student2_validation, student2_final_validation, ...serverState} = w;
        el("json").textContent = JSON.stringify(serverState, null, 2);
        const plan = el("planner"); plan.replaceChildren();
        if (w.plan) {
            paragraph(plan, w.plan.goal);
            list(plan, "Steps", w.plan.steps);
            list(plan, "Acceptance criteria", w.plan.acceptance_criteria);
            paragraph(plan, `Evidence selected: ${(w.plan.required_evidence || []).join(", ") || "none"}`);
            if (w.plan.source === "fallback") paragraph(plan, "The server used a fallback plan because the model's plan could not be parsed.");
        } else paragraph(plan, "Waiting for a plan.");
        const latest = w.attempts?.at(-1);
        window.renderAgentMarkdown(el("worker"), latest?.worker?.response || "Waiting for a response.");
        const review = el("reviewer"); review.replaceChildren();
        if (latest?.review) {
            const r = latest.review;
            paragraph(review, `Verdict: ${r.verdict}`);
            list(review, "Criteria", (r.criteria || []).map(c => `${c.met ? "Met" : "Not met"}: ${c.criterion}${c.note ? ` — ${c.note}` : ""}`));
            list(review, "Risks", r.risks); list(review, "Recommendations", r.recommendations);
            if (r.source === "fallback") paragraph(review, "The server used a fallback review because the model's review could not be parsed.");
        } else paragraph(review, "Waiting for a review.");
        const final = el("final"); final.replaceChildren();
        const d = w.decisions?.at(-1);
        if (d) {
            paragraph(final, `${labels[d.decision] || d.decision} — ${d.reviewer} — ${d.at}`);
            paragraph(final, d.notes || "No review comments.");
            if (w.student2_final_validation) {
                paragraph(final, `Final response checks: ${w.student2_final_validation.status}`);
                if (w.student2_final_validation.issues.length) list(final, "Final response issues", w.student2_final_validation.issues);
            }
            const response = document.createElement("div"); response.className = "agents-markdown";
            window.renderAgentMarkdown(response, w.status === "rejected" ? "No response released." : (w.final_response || "No final response released yet.")); final.append(response);
        } else paragraph(final, "No decision saved yet.");
        updateNotes();
        const validation = w.student2_validation;
        const coverage = validation?.covered_categories || [];
        el("coverage").textContent = coverage.length ? `Included categories: ${coverage.join(", ")}. ${validation.can_accept ? "Place details and recommendation reasons match the supplied evidence." : "Some place details or recommendation reasons need correction; see evidence checks below."} Live availability is not confirmed.` : "No verified category coverage yet.";
        const checked = el("validation"); checked.replaceChildren();
        paragraph(checked, validation ? `${validation.city || "Unverified city"} · ${validation.checked_places} places checked · ${validation.status}` : "City-scoped evidence checks are unavailable for this workflow.");
        if (validation?.issues?.length) list(checked, "Review required", validation.issues);
        paragraph(checked, validation?.scope || "Run a new city-scoped workflow before accepting.");
        checked.classList.toggle("integration-error", !validation?.can_accept);
        const evidence = el("evidence"); evidence.replaceChildren();
        (w.evidence || []).forEach(item => {
            const details = document.createElement("details"); const summary = document.createElement("summary");
            summary.textContent = `[${item.id}] ${item.label}`; const pre = document.createElement("pre"); pre.textContent = item.content;
            details.append(summary, pre); evidence.append(details);
        });
        const stage = {planning: 0, gathering_evidence: 1, working: 2, reviewing: 3, awaiting_human_review: 4}[w.status] ?? (w.status === "failed" ? 0 : 5);
        el("stages").querySelectorAll("li").forEach((node, index) => { node.className = index < stage ? "is-done" : index === stage ? (w.status === "failed" ? "is-failed" : "is-current") : ""; });
        if (w.error) message("message", w.error, true);
        el("log").textContent = "Open Detailed audit log to fetch server history.";
        controls();
        clearTimeout(poll);
        if (!terminal.has(w.status)) poll = setTimeout(() => { if (!busy) action(refresh); }, 2000);
        if (el("log-details").open) loadLog();
    }
    async function loadLog() {
        if (!current) return;
        const id = current.id;
        try {
            const data = await api(`/workflows/${encodeURIComponent(id)}/history`);
            if (current?.id === id) el("log").textContent = JSON.stringify(data.history, null, 2);
        } catch (error) { if (current?.id === id) el("log").textContent = error.message; }
    }
    async function refresh() {
        if (current) {
            render(await api(`/workflows/${encodeURIComponent(current.id)}`));
            message("submission", current.decisions?.length
                ? "Saved decision retrieved from the shared server."
                : "Server state refreshed. No decision saved yet.");
        }
    }
    async function recent() {
        const revision = ++recentRevision;
        el("recent-status").textContent = "Loading recent workflows…";
        try {
            const data = await api("/workflows");
            if (revision !== recentRevision) return;
            el("recent").replaceChildren();
            if (!data.workflows?.length) {
                paragraph(el("recent"), "No saved workflows for student-2.");
            } else {
                const table = document.createElement("table"); table.className = "agents-recent-table";
                const head = document.createElement("thead"); const tr = document.createElement("tr");
                const headers = ["Task", "Status", "Reviewer verdict", "Updated (UTC)", "Action"];
                headers.forEach(label => { const th = document.createElement("th"); th.scope = "col"; th.textContent = label; tr.append(th); });
                head.append(tr); table.append(head); const body = document.createElement("tbody");
                data.workflows.forEach(w => {
                    const row = document.createElement("tr");
                    const task = (w.task || "").split("\n")[0].replace(/^City: [^.]+\.\s*/, "");
                    const states = {awaiting_human_review: "awaiting your review", approved: "approved", partially_accepted: "partially accepted", rejected: "rejected", failed: "failed"};
                    const values = [task.length > 70 ? task.slice(0, 70) + "…" : task, states[w.status] || w.status, w.verdict || "—", (w.updated_at || w.created_at || "").slice(0, 16).replace("T", " ") || "—"];
                    values.forEach((value, n) => {
                        const td = document.createElement("td"); td.dataset.label = headers[n];
                        const node = document.createElement(n === 1 ? "span" : "div"); node.textContent = value;
                        if (n === 0) { node.title = task; const id = document.createElement("small"); id.textContent = w.id; td.append(node, id); }
                        else { if (n === 1) node.className = "pill " + ({approved: "pill-high", rejected: "pill-low", failed: "pill-low", partially_accepted: "pill-medium"}[w.status] || "pill-planned"); td.append(node); }
                        row.append(td);
                    });
                    const td = document.createElement("td"); td.dataset.label = "Action";
                    const button = document.createElement("button"); button.type = "button"; button.className = "btn-sm btn-secondary"; button.textContent = "Open";
                    button.setAttribute("aria-label", `Open workflow ${w.id}`);
                    button.addEventListener("click", () => action(async () => {
                        render(await api(`/workflows/${encodeURIComponent(w.id)}`));
                        message("submission", "Loaded saved server state.");
                    })); td.append(button); row.append(td); body.append(row);
                }); table.append(body); el("recent").append(table);
            }
            message("recent-status", ""); controls();
        } catch (error) {
            if (revision === recentRevision) message("recent-status", `Could not load recent workflows: ${error.message}`, true);
        }
    }
    async function action(fn) {
        if (busy) return;
        busy = true; controls(); message("message", "");
        try { await fn(); }
        catch (error) {
            if (error.workflow) render(error.workflow);
            message("message", error.message, true);
        } finally { busy = false; controls(); }
    }
    async function connection() {
        el("check").disabled = true;
        message("connection", "Checking shared server…");
        try {
            const health = await api("/health");
            message("connection", health.service === "multi-agent-server" && health.status === "running"
                ? "Connected to the shared Multi-Agent server. Model and MCP availability are checked during execution."
                : "The shared server returned an unexpected health status.", health.status !== "running");
        } catch (error) { message("connection", error.message, true); }
        finally { el("check").disabled = false; }
    }
    el("check").addEventListener("click", connection);
    panel.querySelectorAll("[data-agent-sample]").forEach(button => button.addEventListener("click", () => {
        const city = button.dataset.agentSample;
        el("task").value = city === "Melbourne"
            ? "Recommend an activity in Melbourne from recorded place details. Show the place, city, recorded opening hours, recommendation reason and evidence in separate table columns."
            : `Recommend sightseeing places and restaurants in ${city} based on recorded descriptions and ratings. Show each place, city, recorded opening hours and why it is worth visiting.`;
        el("city").value = "";
        el("category").value = "";
        el("name").value = "";
        el("name").value = "";
    }));
    el("run-form").addEventListener("submit", event => {
        event.preventDefault();
        const body = {task: el("task").value.trim(), city: el("city").value, category: el("category").value, name: el("name").value.trim()};
        if (!body.task) return message("message", "Enter a request first.", true);
        action(async () => {
            clearTimeout(poll); current = null;
            el("result-card").hidden = false; el("empty").hidden = true;
            el("notes").value = "";
            el("edited-response").value = "";
            panel.querySelector('[name="agent-decision"][value="Accept"]').checked = true;
            updateNotes();
            el("id").textContent = "Waiting for shared server";
            el("status").textContent = "Running Planner → Worker → Reviewer";
            ["planner", "worker", "reviewer"].forEach(id => el(id).textContent = "Running workflow…");
            el("json").textContent = "Waiting for the server response.";
            el("log").textContent = "Waiting for a new workflow ID.";
            el("final").textContent = "No decision saved for this request.";
            message("submission", ""); controls();
            message("running", "Running… This can take several minutes. The server returns the ID when execution finishes.");
            try {
                render(await api("/workflows", body));
                await recent();
                message("message", "Agent execution finished. Review the results before submitting a decision.");
            } catch (error) {
                el("status").textContent = "Execution not confirmed — check recent workflows";
                throw error;
            } finally { message("running", ""); }
        });
    });
    el("refresh").addEventListener("click", () => action(refresh));
    el("recent-refresh").addEventListener("click", () => action(recent));
    el("resume").addEventListener("click", () => action(async () => {
        const id = el("resume-id").value.trim();
        if (!/^wf-[A-Za-z0-9-]{1,60}$/.test(id)) throw new Error("Enter a valid workflow ID.");
        render(await api(`/workflows/${encodeURIComponent(id)}`));
        message("submission", "Loaded saved server state.");
    }));
    el("log-details").addEventListener("toggle", () => { if (el("log-details").open) loadLog(); });
    const updateNotes = () => {
        const decision = panel.querySelector('[name="agent-decision"]:checked').value;
        el("notes").required = decision !== "Accept";
        el("edit-area").hidden = decision !== "Partially Accept";
        el("edited-response").required = decision === "Partially Accept" && !current?.student2_validation?.can_accept;
    };
    panel.querySelectorAll('[name="agent-decision"]').forEach(radio => radio.addEventListener("change", updateNotes));
    el("review-form").addEventListener("submit", event => {
        event.preventDefault();
        if (!current || current.status !== "awaiting_human_review") return;
        const id = current.id;
        const decision = panel.querySelector('[name="agent-decision"]:checked').value;
        const body = {decision, reviewer: el("reviewer-name").value.trim(), notes: el("notes").value.trim(), final_response: decision === "Partially Accept" ? el("edited-response").value.trim() : ""};
        if (!body.reviewer || (decision !== "Accept" && !body.notes)) return message("submission", "Enter your reviewer name and required comments.", true);
        action(async () => {
            message("submission", "Submitting decision and checking saved server state…");
            try {
                await api(`/workflows/${encodeURIComponent(id)}/decision`, body);
                const saved = await api(`/workflows/${encodeURIComponent(id)}`);
                render(saved);
                const d = saved.decisions?.at(-1);
                if (saved.status !== finalStatuses[d?.decision] || labels[d?.decision] !== decision || d.reviewer !== body.reviewer || (d.notes || "") !== body.notes || (body.final_response && saved.final_response !== body.final_response)) {
                    throw new Error("The returned server state did not confirm this decision. Refresh workflow status before retrying.");
                }
                message("submission", "Decision saved and confirmed by reading it back from the shared server.");
                await recent();
            } catch (error) {
                message("submission", "Save not confirmed. Refresh workflow status to check before submitting again.", true);
                throw error;
            }
        });
    });
    controls(); connection(); recent(); fillReviewerName();
};
