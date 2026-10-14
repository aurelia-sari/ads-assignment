/* Browser regression tests against real HTML/CSS/JS with mocked gateway responses.
   NODE_PATH=<playwright packages> node student-2/tests/test_agents_ui.cjs
   Uses installed Chrome; set CHROME_PATH when needed. No live model calls. */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const repo = path.dirname(root);
const json = (route, data, status = 200) => route.fulfill({status, contentType: "application/json", body: JSON.stringify(data)});
const hostile = '<img src=x onerror="window.agentXss=true">';
const labels = {Accept: "approve", "Partially Accept": "partial", Reject: "reject"};
const statuses = {approve: "approved", partial: "partially_accepted", reject: "rejected"};
const fixture = id => ({id, feature: "student-2", task: "Plan Sydney", status: "awaiting_human_review", round: 1,
    verdict: "concerns", updated_at: "2026-10-11T10:27:14+00:00",
    plan: {goal: "Sydney day out " + hostile, steps: ["Search places", "Recommend"], acceptance_criteria: ["Cite evidence"], required_evidence: ["S1"]},
    evidence: [{id: "E1", ok: true, content: "Sydney Opera House"}],
    attempts: [{worker: {response: "**Morning**\n\n* Sydney Opera House [E1]. " + hostile + "\n\n| Place | City | Opening hours | Reason | Evidence |\n| --- | --- | --- | --- | --- |\n| Sydney Opera House | Sydney | 09:00-17:00 | Harbour | [E1] |"}, review: {verdict: "concerns", criteria: [{criterion: "Cite evidence", met: true, note: "E1 cited"}], risks: ["Opening hours unknown"], recommendations: ["Check availability"]}}],
    student2_validation: {city: "Sydney", status: "checked", can_accept: true, covered_categories: ["attraction", "restaurant"], checked_places: 1, issues: [], scope: "Recorded hours only"},
    decisions: [], final_response: null});

(async () => {
    const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"});
    try {
        const page = await browser.newPage({viewport: {width: 1280, height: 900}});
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        let current = fixture("wf-existing"), count = 0, holdRun = false, releaseRun, failRead = false, failDecision = false, offline = false;
        let posted;
        let sessionUser = {id:15, name:"Kevin Kim"}, failSession = false, delayedSession = false;
        await page.route("**/*", async route => {
            const url = new URL(route.request().url());
            const pathname = url.pathname;
            if (url.hostname !== "student2.test") return route.abort();
            if (pathname === "/shared/js/auth-guard.js") return route.fulfill({contentType: "text/javascript", body: 'window.NextStopAuthGuard={guardPage:()=>{document.querySelector("main").style.display="block"}};'});
            if (pathname === "/student-4/session.js") return route.fulfill({contentType: "text/javascript", body: `window.NextStopSession={verifySession:async()=>{${delayedSession ? 'return window.sessionPromise ||= new Promise(resolve => window.finishSession = () => resolve({id:15,name:"Delayed Name"}));' : failSession ? 'return null;' : 'return ' + JSON.stringify(sessionUser) + ';'}}};`});
            if (pathname.startsWith("/api/student-2/agents")) {
                const endpoint = pathname.slice("/api/student-2/agents".length);
                if (endpoint === "/health") return json(route, offline ? {error: "Shared server offline"} : {service: "multi-agent-server", status: "running"}, offline ? 503 : 200);
                if (endpoint === "/workflows" && route.request().method() === "POST") {
                    posted = route.request().postDataJSON(); current = fixture(`wf-test-${++count}`);
                    if (holdRun) await new Promise(resolve => releaseRun = resolve);
                    return json(route, current, 201);
                }
                if (endpoint === "/workflows") return json(route, {workflows: current ? [current] : []});
                if (endpoint.endsWith("/history")) return json(route, {history: [{actor: "planner", event: "plan", detail: hostile}]});
                if (endpoint.endsWith("/decision")) {
                    if (failDecision) return json(route, {error: "Decision refused"}, 409);
                    const body = route.request().postDataJSON();
                    const decision = labels[body.decision];
                    current.status = statuses[decision];
                    current.decisions = [{decision, reviewer: body.reviewer, notes: body.notes, at: "2026-10-11T00:00:00Z"}];
                    current.final_response = decision === "reject" ? null : (body.final_response || current.attempts[0].worker.response);
                    return json(route, current);
                }
                if (failRead) return json(route, {error: "Read-back unavailable"}, 503);
                return json(route, current);
            }
            if (pathname.startsWith("/api/student-2/")) return route.fulfill({contentType: "text/html", body: '<p class="muted">Existing feature fixture</p>'});
            let file;
            if (pathname.startsWith("/shared/")) file = path.join(repo, pathname);
            else file = path.join(root, "frontend", pathname === "/" ? "templates/index.html" : pathname);
            try {
                const body = await fs.readFile(file);
                const ext = path.extname(file);
                return route.fulfill({body, contentType: ext === ".css" ? "text/css" : ext === ".js" ? "text/javascript" : "text/html"});
            } catch (_) { return route.fulfill({status: 404, body: "Not found"}); }
        });
        await page.goto("http://student2.test/");
        await page.locator('[data-tab="agents"]').click();
        await page.locator("#agents-task").waitFor();
        await page.waitForFunction(() => document.querySelector("#agents-connection").textContent.includes("Connected"));
        assert.equal(await page.locator("#agents-reviewer-name").isDisabled(), true);
        await page.waitForFunction(() => document.querySelector("#agents-reviewer-name").value === "Kevin Kim");
        assert.equal(await page.locator("#agents-city").inputValue(), "");
        assert.equal(await page.locator("#agents-category").inputValue(), "");
        await page.locator("#agents-recent tbody tr").waitFor();
        assert.equal(await page.locator("#agents-result-card").isVisible(), false);
        assert.equal(await page.locator("#agents-empty").isVisible(), true);
        assert.equal(await page.locator("#agents-recent thead th").count(), 5);
        assert.equal(await page.locator("#agents-recent button").textContent(), "Open");
        await page.locator("#agents-recent button").click();
        await page.waitForFunction(() => document.querySelector("#agents-id").textContent === "wf-existing");
        for (const city of ["Sydney", "Tokyo", "Melbourne"]) {
            await page.locator(`[data-agent-sample="${city}"]`).click();
            assert.ok((await page.locator("#agents-task").inputValue()).includes(city));
            assert.equal(await page.locator("#agents-city").inputValue(), "");
            assert.equal(await page.locator("#agents-category").inputValue(), "");
            assert.equal(await page.locator("#agents-name").inputValue(), "");
        }
        holdRun = true;
        await page.locator('[data-agent-sample="Sydney"]').click();
        await page.locator("#agents-run").click();
        await page.waitForFunction(() => document.querySelector("#agents-running").textContent.includes("Running"));
        assert.equal(await page.locator("#agents-submit").isDisabled(), true);
        assert.equal(await page.locator("#agents-run").isDisabled(), true);
        await page.locator('[data-tab="places"]').click();
        await page.locator('[data-tab="agents"]').click();
        releaseRun(); holdRun = false;
        await page.waitForFunction(() => !document.querySelector("#agents-reviewer-name").disabled && !document.querySelector("#agents-review-fields").disabled);
        await page.waitForFunction(() => document.querySelector("#agents-recent").textContent.includes("wf-test-1"));
        assert.ok((await page.locator("#agents-coverage").textContent()).includes("attraction, restaurant"));
        assert.equal(posted.city, ""); assert.equal(posted.category, ""); assert.ok(posted.task.includes("Sydney"));
        assert.ok((await page.locator("#agents-worker").textContent()).includes(hostile));
        assert.equal(await page.locator("#panel-agents img").count(), 0);
        assert.equal(await page.locator("#agents-worker strong").first().textContent(), "Morning");
        assert.equal(await page.locator("#agents-worker ul li").count(), 1);
        assert.equal(await page.locator("#agents-worker table tbody tr").count(), 1);
        assert.equal(await page.evaluate(() => window.agentXss), undefined);
        await page.locator("#agents-log-details summary").click();
        await page.waitForFunction(() => document.querySelector("#agents-log").textContent.includes('"actor"'));
        assert.ok((await page.locator("#agents-log").textContent()).includes("planner"));
        for (const choice of ["Accept", "Partially Accept", "Reject"]) {
            if (choice !== "Accept") {
                await page.locator("#agents-run").click();
                await page.waitForFunction(() => !document.querySelector("#agents-review-fields").disabled);
            }
            await page.locator(`[name="agent-decision"][value="${choice}"]`).check();
            assert.equal(await page.locator("#agents-notes").evaluate(node => node.required), choice !== "Accept");
            if (choice !== "Accept") await page.locator("#agents-reviewer-name").fill("Kevin");
            else assert.equal(await page.locator("#agents-reviewer-name").inputValue(), "Kevin Kim");
            await page.locator("#agents-notes").fill("Checked evidence " + choice);
            await page.locator("#agents-submit").click();
            await page.waitForFunction(() => document.querySelector("#agents-submission").textContent.includes("saved and confirmed"));
            assert.ok((await page.locator("#agents-final").textContent()).includes(choice));
            if (choice === "Accept") assert.equal(current.decisions[0].reviewer, "Kevin Kim");
            await page.waitForFunction(() => !document.querySelector("#agents-recent-status").textContent);
            assert.ok((await page.locator("#agents-recent").textContent()).includes({Accept: "approved", "Partially Accept": "partially accepted", Reject: "rejected"}[choice]));
            assert.equal(await page.locator("#agents-submit").isDisabled(), true);
            assert.ok((await page.locator("#agents-final").textContent()).includes(choice === "Reject" ? "No response released" : "Sydney Opera House"));
        }
        await page.locator("#agents-run").click();
        await page.waitForFunction(() => !document.querySelector("#agents-review-fields").disabled);
        await page.locator('[name="agent-decision"][value="Accept"]').check();
        failDecision = true;
        await page.locator("#agents-submit").click();
        await page.waitForFunction(() => document.querySelector("#agents-submission").textContent.includes("Save not confirmed"));
        assert.ok(!(await page.locator("#agents-submission").textContent()).includes("saved and confirmed"));
        assert.equal(await page.locator("#agents-submit").isDisabled(), false);
        failDecision = false; failRead = true;
        await page.locator("#agents-submit").click();
        await page.waitForFunction(() => document.querySelector("#agents-message").textContent.includes("Read-back unavailable"));
        assert.ok((await page.locator("#agents-submission").textContent()).includes("Save not confirmed"));
        failRead = false;
        await page.locator("#agents-refresh").click();
        await page.waitForFunction(() => document.querySelector("#agents-status").textContent === "approved");
        assert.equal(await page.locator("#agents-submit").isDisabled(), true);
        assert.ok((await page.locator("#agents-submission").textContent()).includes("retrieved from the shared server"));
        const longId = "wf-" + "a".repeat(60);
        current.id = longId; current.attempts[0].worker.response = "x".repeat(3000);
        await page.locator("#agents-refresh").click();
        await page.waitForFunction(() => document.querySelector("#agents-id").textContent.length > 60);
        await page.locator("#agents-result-card > details:not(#agents-log-details) summary").click();
        await page.locator("#agents-progress-heading").evaluate(node => node.parentElement.querySelector("summary").click());
        await page.locator("#agents-recent-refresh").click();
        await page.locator("#agents-recent button").waitFor();
        for (const width of [1280, 760, 360, 320]) {
            await page.setViewportSize({width, height: 900});
            const sizes = await page.evaluate(() => ({width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth}));
            assert.ok(sizes.scroll <= sizes.width, `Horizontal overflow at ${width}: ${JSON.stringify(sizes)}`);
        }
        if (process.env.AGENTS_SCREENSHOT) await page.screenshot({path: process.env.AGENTS_SCREENSHOT, fullPage: true});
        for (const tab of ["places", "favourites", "ai", "mcp", "rag", "agents"]) {
            await page.locator(`[data-tab="${tab}"]`).click();
            assert.equal(await page.locator(`#panel-${tab}`).isVisible(), true);
        }
        current.status = "awaiting_human_review"; current.decisions = []; current.final_response = null;
        current.student2_validation = {city: "Sydney", status: "concerns", can_accept: false, checked_places: 1, issues: ["Opening hours do not match evidence"], scope: "Recorded hours only"};
        await page.locator("#agents-refresh").click();
        await page.waitForFunction(() => document.querySelector("#agents-validation").textContent.includes("do not match"));
        assert.equal(await page.locator('[name="agent-decision"][value="Accept"]').isDisabled(), true);
        assert.ok(!(await page.locator("#agents-coverage").textContent()).includes("reasons match"));
        await page.locator('[name="agent-decision"][value="Partially Accept"]').check();
        assert.equal(await page.locator("#agents-edit-area").isVisible(), true);
        assert.equal(await page.locator("#agents-edited-response").evaluate(node => node.required), true);
        await page.locator("#agents-edited-response").fill("| Place | City | Opening hours | Reason | Evidence |\n| --- | --- | --- | --- | --- |\n| Sydney Opera House | Sydney | 09:00-17:00 | Harbour | [E1] |");
        await page.locator("#agents-notes").fill("Fixed hours");
        await page.locator("#agents-submit").click();
        await page.waitForFunction(() => document.querySelector("#agents-submission").textContent.includes("saved and confirmed"));
        assert.equal(await page.locator("#agents-final table").count(), 1);
        offline = true;
        await page.locator("#agents-check").click();
        await page.waitForFunction(() => document.querySelector("#agents-connection").textContent.includes("offline"));
        const safeMarkdown = await page.evaluate(() => {
            const div = document.createElement("div");
            window.renderAgentMarkdown(div, '**Bold**\n\n# Heading\n\n1. One\n\n[Click](javascript:alert(1)) <script>alert(1)</script>\n\n```html\n<img src=x onerror=alert(1)>\n```');
            return {strong: div.querySelectorAll("strong").length, heading: div.querySelectorAll("h3").length, list: div.querySelectorAll("ol li").length, code: div.querySelectorAll("pre code").length, unsafe: div.querySelectorAll("a,script,img").length};
        });
        assert.deepEqual(safeMarkdown, {strong: 1, heading: 1, list: 1, code: 1, unsafe: 0});
        offline = false;
        for (const state of [null, {id:15}, "unavailable", "delayed"]) {
            sessionUser = typeof state === "string" ? null : state;
            delayedSession = state === "delayed";
            failSession = state === "unavailable";
            current = fixture("wf-manual-review");
            await page.reload();
            await page.locator('[data-tab="agents"]').click();
            await page.locator("#agents-recent button").waitFor();
            await page.locator("#agents-recent button").click();
            await page.waitForFunction(() => !document.querySelector("#agents-review-fields").disabled);
            assert.equal(await page.locator("#agents-reviewer-name").inputValue(), "");
            await page.locator("#agents-reviewer-name").fill("Guest Reviewer");
            if (delayedSession) {
                await page.evaluate(() => window.finishSession());
                await page.waitForFunction(() => document.querySelector("#agents-reviewer-hint").textContent.startsWith("Enter your name"));
                assert.equal(await page.locator("#agents-reviewer-name").inputValue(), "Guest Reviewer");
            }
            await page.locator("#agents-submit").click();
            await page.waitForFunction(() => document.querySelector("#agents-submission").textContent.includes("saved and confirmed"));
            assert.equal(current.decisions[0].reviewer, "Guest Reviewer");
        }
        assert.deepEqual(errors, []);
        console.log("PASS: verified-session reviewer autofill, guest/missing-name/session-failure manual submission, safe Markdown headings/lists/tables/code, invalid-result locking and partial correction, saved decisions/read-back, logs, six tabs, no horizontal overflow at 1280/760/360/320px.");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
