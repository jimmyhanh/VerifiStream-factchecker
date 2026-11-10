const sample = {status: "completed", results: [{
  proposition_text: "The workshop added a Saturday session.",
  evidence_status: "Supported",
  explanation: "The updated timetable directly lists the extra session.",
  citations: [{title: "Illustrative workshop timetable", relationship: "supports",
    quote: "An additional workshop will meet on Saturday at 10 a.m."}]
}]};
const results = document.querySelector("#results");
const statusLine = document.querySelector("#status");
function add(parent, tag, value) {
  const el = document.createElement(tag);
  el.textContent = value;
  parent.append(el);
  return el;
}
function render(run, name) {
  if (run?.status !== "completed" || !Array.isArray(run.results))
    throw Error("Choose a completed verification or confidence run JSON.");
  const fragment = document.createDocumentFragment();
  for (const row of run.results) {
    if (!row || !(typeof row.evidence_status === "string" || Number.isFinite(row.evidence_confidence)))
      throw Error("This file does not contain verification or confidence findings.");
    const card = document.createElement("article");
    fragment.append(card);
    add(card, "small", row.evidence_status || "Evidence confidence");
    add(card, "h2", row.proposition_text || row.proposition_id || "Proposition");
    if (row.explanation) add(card, "p", row.explanation);
    if (Number.isFinite(row.evidence_confidence))
      add(card, "p", row.evidence_confidence + "% evidence confidence · experimental, uncalibrated");
    for (const c of row.citations || []) {
      add(card, "blockquote", c.quote);
      const caption = c.title || c.publisher || "Source";
      const source = add(card, /^https?:\/\//i.test(c.url || "") ? "a" : "span", caption);
      if (source.tagName === "A") { source.href = c.url; source.target = "_blank"; source.rel = "noopener noreferrer"; }
      if (c.relationship) add(card, "small", " · " + c.relationship);
    }
    for (const limit of row.limitations || []) add(card, "p", limit);
  }
  results.replaceChildren(fragment);
  statusLine.textContent = name + " · " + run.results.length + " findings";
}
let selection = 0;
document.querySelector("#sample").onclick = () => { selection++; render(sample, "Fictional sample"); };
document.querySelector("#file").onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  const current = ++selection;
  try {
    const data = await file.text();
    if (current === selection) render(JSON.parse(data), file.name);
  } catch (error) {
    if (current === selection) {
      results.replaceChildren();
      statusLine.textContent = error instanceof SyntaxError ? "This file contains invalid JSON." : error.message;
    }
  }
};
render(sample, "Fictional sample");
