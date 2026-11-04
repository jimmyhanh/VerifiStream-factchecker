import type {
  RetrievalRun,
  MappingRun,
  ConfidenceResult,
  Assessment,
} from "./types";
export function screeningIds(run: RetrievalRun): string[] {
  // Round robin across propositions; within each, lexical match is only a triage signal.
  const queues = run.results.map((r) =>
    [...r.passages].sort((a, b) => b.lexical_relevance - a.lexical_relevance),
  );
  const ids: string[] = [];
  while (ids.length < 12 && queues.some((q) => q.length))
    for (const q of queues) {
      const p = q.shift();
      if (p && !ids.includes(p.id)) ids.push(p.id);
      if (ids.length === 12) break;
    }
  return ids;
}
export function evidencePriority(
  result?: MappingRun["results"][number],
): number {
  if (!result || result.status !== "mapped") return 2;
  switch (result.decision?.relationship) {
    case "SUPPORTS":
    case "CONTRADICTS":
    case "QUALIFIES":
      return 0;
    case "CONTEXT":
      return 1;
    case "IRRELEVANT":
      return 3;
    default:
      return 2;
  }
}
export function confidenceLevel(score: number): string {
  return score < 25
    ? "Very limited"
    : score < 50
      ? "Low"
      : score < 75
        ? "Moderate"
        : "High";
}
export function evidenceGaps(p: Assessment): string[] {
  const gaps: string[] = [];
  if (p.coverage.unresolved_passage_ids.length)
    gaps.push(
      `${p.coverage.unresolved_passage_ids.length} selected passage(s) could not be assessed. Resolve mapping errors or review them before treating this as a complete assessment.`,
    );
  if (p.coverage.unmapped_passage_ids.length)
    gaps.push(
      `${p.coverage.unmapped_passage_ids.length} retrieved passage(s) were outside this assessment. They may contain additional or disagreeing evidence.`,
    );
  if (p.coverage.failed_fetch_count)
    gaps.push(
      `${p.coverage.failed_fetch_count} source fetch(es) failed; retrieval coverage is incomplete.`,
    );
  if (
    !p.citations.some((c) =>
      ["SUPPORTS", "CONTRADICTS", "QUALIFIES"].includes(c.relationship),
    )
  )
    gaps.push(
      "No selected passage provides direct support, contradiction or qualification. Context and keyword matches alone cannot establish the claim.",
    );
  if (p.evidence_status === "Conflicting Evidence")
    gaps.push(
      "Sources disagree. Inspect the opposing passages, dates, measures and scope.",
    );
  return gaps;
}
