/* Deliberately small Markdown renderer. No raw HTML, images, or active links. */
window.renderAgentMarkdown = function (target, source) {
    target.replaceChildren();
    const inline = (parent, text) => {
        const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*)/g;
        let pos = 0;
        for (const match of text.matchAll(pattern)) {
            parent.append(document.createTextNode(text.slice(pos, match.index)));
            const token = match[0];
            const tag = token.startsWith("`") ? "code" : token.startsWith("**") ? "strong" : "em";
            const node = document.createElement(tag);
            node.textContent = token.slice(tag === "strong" ? 2 : 1, tag === "strong" ? -2 : -1);
            parent.append(node); pos = match.index + token.length;
        }
        parent.append(document.createTextNode(text.slice(pos)));
    };
    const cells = line => line.trim().replace(/^\||\|$/g, "").split("|").map(s => s.trim());
    const lines = String(source || "").split(/\r?\n/);
    for (let i = 0; i < lines.length;) {
        let line = lines[i];
        if (!line.trim()) { i++; continue; }
        if (line.startsWith("```")) {
            const pre = document.createElement("pre"); const code = document.createElement("code"); const block = [];
            i++; while (i < lines.length && !lines[i].startsWith("```")) block.push(lines[i++]);
            i++; code.textContent = block.join("\n"); pre.append(code); target.append(pre); continue;
        }
        if (line.includes("|") && i+1 < lines.length && cells(lines[i+1]).every(c => /^:?-{3,}:?$/.test(c))) {
            const table = document.createElement("table"); const head = document.createElement("thead");
            const tr = document.createElement("tr"); const headers = cells(line);
            headers.forEach(text => { const th = document.createElement("th"); th.scope = "col"; inline(th, text); tr.append(th); });
            head.append(tr); table.append(head); const body = document.createElement("tbody"); i += 2;
            while (i < lines.length && lines[i].includes("|")) {
                const row = document.createElement("tr");
                cells(lines[i++]).forEach((text, n) => { const td = document.createElement("td"); td.dataset.label = headers[n] || "Detail"; inline(td, text); row.append(td); });
                body.append(row);
            }
            table.append(body); target.append(table); continue;
        }
        const heading = line.match(/^(#{1,6})\s+(.+)/);
        if (heading) { const node = document.createElement("h"+ Math.min(6, heading[1].length+2)); inline(node, heading[2]); target.append(node); i++; continue; }
        const bullet = line.match(/^\s*(?:[-*+] |\d+[.)] )(.+)/);
        if (bullet) {
            const ol = /^\s*\d/.test(line); const list = document.createElement(ol ? "ol" : "ul");
            while (i < lines.length) {
                const item = lines[i].match(ol ? /^\s*\d+[.)] (.+)/ : /^\s*[-*+] (.+)/);
                if (!item) break;
                const li = document.createElement("li"); inline(li, item[1]); list.append(li); i++;
            }
            target.append(list); continue;
        }
        const p = document.createElement("p"); inline(p, line); target.append(p); i++;
    }
};
