
    (function () {
        NextStopAuthGuard.guardPage({ mainSelector: "main.app-shell" });
    })();
    



    // Load each fragment once, retaining form values and results across tab switches.
    // The outer panels stay in the page so the existing navigation remains unchanged.
    const fragmentLoads = new WeakMap();
    function loadTabFragment(panel) {
        if (!panel || !panel.dataset.fragment) return Promise.resolve();
        if (fragmentLoads.has(panel)) return fragmentLoads.get(panel);
        const pending = fetch(panel.dataset.fragment)
            .then(async response => {
                if (!response.ok) throw new Error("Could not load tab");
                const html = await response.text();
                // nginx falls back to index.html when an asset is missing.
                if (/<!doctype|<html[\s>]/i.test(html)) throw new Error("Missing tab fragment");
                panel.innerHTML = html;
                htmx.process(panel);
            })
            .catch(error => {
                fragmentLoads.delete(panel);
                panel.innerHTML = '<p class="notice notice-error">Could not load this tab. Please reload the page to try again.</p>';
                throw error;
            });
        fragmentLoads.set(panel, pending);
        return pending;
    }

    const tabButtons =
        document.querySelectorAll(".tab-btn");

    const tabPanels =
        document.querySelectorAll(".tab-panel");


    tabButtons.forEach(button => {

        button.addEventListener("click", () => {

            const selectedTab =
                button.dataset.tab;


            tabButtons.forEach(tabButton => {
                tabButton.classList.remove("is-active");
            });


            tabPanels.forEach(panel => {
                panel.classList.remove("is-active");
            });


            button.classList.add("is-active");


            const selectedPanel =
                document.getElementById(
                    `panel-${selectedTab}`
                );


            if (selectedPanel) {
                selectedPanel.classList.add("is-active");
            }

            if (selectedTab === "favourites") {
                loadFavourites();
            }
        });

    });

    async function addFavourite(placeId) {
        const user = await NextStopSession.verifySession();

        if (!user) {
            alert("Please sign in to add favourites.");
            return;
        }

        try {
            const response = await fetch("/api/student-2/favourites", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    place_id: placeId,
                    user_id: user.id
                })
            });

            if (!response.ok) {
                if (response.status === 400) {
                    alert("This place is already in your favourites.");
                } else if (response.status === 401) {
                    alert("Please sign in to add favourites.");
                } else {
                    alert("Could not add this place to your favourites.");
                }

                return;
            }

            alert("Added to favourites.");
            await loadFavourites();

        } catch (error) {
            alert("Could not add favourite.");
        }
    }

    async function deleteFavourite(favouriteId) {
        const user = await NextStopSession.verifySession();

        if (!user) {
            alert("Please sign in to delete favourites.");
            return;
        }

        const confirmed = confirm(
            "Remove this place from favourites?"
        );

        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch(
                `/api/student-2/favourites/${favouriteId}`,
                {
                    method: "DELETE",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        user_id: user.id
                    })
                }
            );

        if (!response.ok) {
            if (response.status === 404) {
                alert("You can only remove your own favourites.");
            } else {
                alert("Could not remove this favourite.");
            }

            return;
        }

        alert("Removed from favourites.");
        await loadFavourites();

        } catch (error) {
            alert("Could not delete favourite.");
        }
    }

async function loadFavourites() {
    try {
        await loadTabFragment(document.getElementById("panel-favourites"));
    } catch (error) {
        return;
    }
    const user = await NextStopSession.verifySession();

    const favouritesList =
        document.getElementById("favourites-list");

    if (!user) {
        favouritesList.innerHTML = `
            <div class="notice">
                Please sign in to view your favourites.
            </div>
        `;
        return;
    }

    try {
        const response = await fetch(
            `/api/student-2/favourites?user_id=${user.id}`
        );

        if (!response.ok) {
            favouritesList.innerHTML = `
                <div class="notice notice-error">
                    Could not load favourites.
                </div>
            `;
            return;
        }

        favouritesList.innerHTML =
            await response.text();

    } catch (error) {
        favouritesList.innerHTML = `
            <div class="notice notice-error">
                Could not load favourites.
            </div>
        `;
    }
}

async function submitAiRecommendation(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const questionInput =
        form.querySelector('[name="question"]');

    const result =
        document.getElementById("recommendation-result");

    const question = questionInput.value.trim();

    if (!question) {
        return;
    }

    const user = await NextStopSession.verifySession();

    const payload = {
        question: question
    };

    if (user) {
        payload.user_id = user.id;
    }

    result.innerHTML = `
        <p class="muted">
            Thinking...
        </p>
    `;

    try {
        const response = await fetch(
            "/api/student-2/ai/recommend",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "HX-Request": "true"
                },
                body: JSON.stringify(payload)
            }
        );

        if (!response.ok) {
            result.innerHTML = `
                <div class="notice notice-error">
                    Could not generate a recommendation.
                </div>
            `;
            return;
        }

        result.innerHTML = await response.text();
        form.reset();

    } catch (error) {
        result.innerHTML = `
            <div class="notice notice-error">
                Could not generate a recommendation.
            </div>
        `;
    }
}

function initialiseFrontendMode(panelId, toggleId, statusId) {
    const panel = document.getElementById(panelId);
    const toggle = document.getElementById(toggleId);
    const status = document.getElementById(statusId);

    if (!panel || !toggle || !status) {
        return;
    }

    const controls = panel.querySelectorAll(
        'input:not([type="checkbox"]), button'
    );

    const updateMode = () => {
        controls.forEach(control => {
            control.disabled = !toggle.checked;
        });
        status.textContent = toggle.checked ? "ON" : "OFF";
        status.classList.toggle("is-on", toggle.checked);
    };

    toggle.addEventListener("change", updateMode);
    updateMode();
}

function showResultMessage(resultId, message, isError = false) {
    const result = document.getElementById(resultId);
    if (!result) return;
    const paragraph = document.createElement("p");
    paragraph.className = isError ? "integration-error" : "muted";
    paragraph.textContent = message;
    result.replaceChildren(paragraph);
}

async function requestJson(path, body = {}) {
    let response;
    try {
        response = await fetch(`/api/student-2${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
    } catch (error) {
        throw new Error("The Student 2 service is unavailable.");
    }

    let payload;
    try {
        payload = await response.json();
    } catch (error) {
        throw new Error("The service returned an invalid response.");
    }
    if (!response.ok) {
        throw new Error(payload.error || payload.detail || "The request failed.");
    }
    return payload;
}

async function runBusy(button, action) {
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Working...";
    try {
        await action();
    } finally {
        button.textContent = originalText;
        const panel = button.closest(".tab-panel");
        const toggle = panel && panel.querySelector('.mode-switch input[type="checkbox"]');
        button.disabled = !toggle || !toggle.checked;
    }
}

function renderPlaceResults(result) {
    const target = document.getElementById("mcp-result");
    const structured = result.structuredContent || {};
    const rows = Array.isArray(structured.rows) ? structured.rows : [];
    if (!rows.length) {
        showResultMessage("mcp-result", "No matching places found.");
        return;
    }

    const summary = document.createElement("p");
    summary.className = "result-summary";
    summary.textContent = `${structured.row_count ?? rows.length} place${rows.length === 1 ? "" : "s"} found${structured.truncated ? " (results limited)" : ""}.`;
    const list = document.createElement("div");
    list.className = "integration-result-list";
    rows.forEach(place => {
        const card = document.createElement("article");
        card.className = "integration-result-card";
        const title = document.createElement("h4");
        title.textContent = place.name || "Unnamed place";
        const details = document.createElement("p");
        details.textContent = [place.category, place.address].filter(Boolean).join(" · ");
        card.append(title, details);
        if (place.rating !== undefined && place.rating !== null) {
            const rating = document.createElement("p");
            rating.textContent = `Rating: ${place.rating}`;
            card.append(rating);
        }
        list.append(card);
    });
    target.replaceChildren(summary, list);
}

function citationList(items, emptyMessage) {
    if (!Array.isArray(items) || !items.length) {
        const paragraph = document.createElement("p");
        paragraph.className = "muted";
        paragraph.textContent = emptyMessage;
        return paragraph;
    }
    const list = document.createElement("ol");
    list.className = "citation-list";
    items.forEach(item => {
        const entry = document.createElement("li");
        const source = [item.source, item.section].filter(Boolean).join(" — ");
        entry.textContent = item.excerpt ? `${source}: ${item.excerpt}` : source;
        list.append(entry);
    });
    return list;
}

function initialiseMcp() {
    initialiseFrontendMode("panel-mcp", "mcp-enabled", "mcp-mode-status");
    const button = document.getElementById("mcp-run-tool");
    if (!button) return;
    button.addEventListener("click", () => runBusy(button, async () => {
        const category = document.getElementById("mcp-category").value.trim();
        const name = document.getElementById("mcp-name").value.trim();
        if (!category) {
            showResultMessage("mcp-result", "Enter a category first.", true);
            return;
        }
        showResultMessage("mcp-result", "Searching places...");
        try {
            renderPlaceResults(await requestJson("/mcp/search-places", { category, name }));
        } catch (error) {
            showResultMessage("mcp-result", error.message, true);
        }
    }));
}

function initialiseRag() {
    initialiseFrontendMode("panel-rag", "rag-enabled", "rag-mode-status");

    const refresh = document.getElementById("rag-refresh-knowledge");
    refresh?.addEventListener("click", () => runBusy(refresh, async () => {
        showResultMessage("rag-context", "Refreshing knowledge...");
        try {
            const result = await requestJson("/rag/reindex");
            const count = result.chunks ?? result.documents ?? result.files;
            showResultMessage("rag-context", count === undefined
                ? "Knowledge refreshed successfully."
                : `Knowledge refreshed successfully (${count} indexed).`);
        } catch (error) {
            showResultMessage("rag-context", error.message, true);
        }
    }));

    const retrieve = document.getElementById("rag-retrieve-context");
    retrieve?.addEventListener("click", () => runBusy(retrieve, async () => {
        const query = document.getElementById("rag-query").value.trim();
        if (!query) {
            showResultMessage("rag-context", "Enter a retrieval query first.", true);
            return;
        }
        showResultMessage("rag-context", "Retrieving context...");
        try {
            const result = await requestJson("/rag/search", { query });
            const target = document.getElementById("rag-context");
            const summary = document.createElement("p");
            summary.className = "result-summary";
            summary.textContent = `Confidence: ${result.confidence || "unknown"}. ${result.confidence_reason || ""}`.trim();
            target.replaceChildren(summary, citationList(result.hits, "No relevant context found."));
        } catch (error) {
            showResultMessage("rag-context", error.message, true);
        }
    }));

    const answerButton = document.getElementById("rag-answer-question");
    answerButton?.addEventListener("click", () => runBusy(answerButton, async () => {
        const question = document.getElementById("rag-question").value.trim();
        if (!question) {
            showResultMessage("rag-answer", "Enter a question first.", true);
            return;
        }
        showResultMessage("rag-answer", "Preparing a grounded answer...");
        try {
            const result = await requestJson("/rag/ask", { question });
            showResultMessage("rag-answer", result.answer || "No answer returned.");
            showResultMessage(
                "rag-confidence",
                `${result.confidence || "unknown"}${result.confidence_reason ? ` — ${result.confidence_reason}` : ""}`
            );
            document.getElementById("rag-sources-citations").replaceChildren(
                citationList(result.citations, "No supporting sources.")
            );
        } catch (error) {
            showResultMessage("rag-answer", error.message, true);
            showResultMessage("rag-confidence", "Unavailable");
            showResultMessage("rag-sources-citations", "No supporting sources.");
        }
    }));
}

function initialiseFrontendModes() {
    initialiseMcp();
    initialiseRag();
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        // Independent panels must not delay the initial favourites request.
        Promise.allSettled(
            Array.from(document.querySelectorAll("[data-fragment]"), loadTabFragment)
        ).then(initialiseFrontendModes);
        loadFavourites();
    }
);
