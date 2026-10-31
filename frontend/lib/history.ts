import { AnyRun, History, Selection, Stage, Runs, stages } from "./types";
function parent(stage: Stage, run: AnyRun): [Stage, string] | null {
  switch (stage) {
    case "transcript":
      return null;
    case "claims":
      return ["transcript", (run as Runs["claims"]).transcript_run_id];
    case "atoms":
      return ["claims", (run as Runs["atoms"]).claim_run_id];
    case "retrieval":
      return ["atoms", (run as Runs["retrieval"]).decomposition_run_id];
    case "mapping":
      return ["retrieval", (run as Runs["mapping"]).request.retrieval_run_id];
    case "ranking":
      return ["mapping", (run as Runs["ranking"]).request.mapping_run_id];
    case "verification":
      return ["ranking", (run as Runs["verification"]).request.ranking_run_id];
    case "confidence":
      return [
        "verification",
        (run as Runs["confidence"]).request.verification_run_id,
      ];
  }
}
/** Resolve an exact ancestry; never attach unrelated latest runs. */
export function selectHistory(
  history: History,
  stage: Stage,
  run: AnyRun,
): Selection {
  const selected: Selection = {};
  function visit(key: Stage, item: AnyRun) {
    Object.assign(selected, { [key]: item });
    const ancestor = parent(key, item);
    if (ancestor) {
      const source = history[ancestor[0]].find((r) => r.id === ancestor[1]);
      if (!source)
        throw new Error(
          "A saved parent run is missing. Refresh the library; this result cannot be combined with unrelated runs.",
        );
      visit(ancestor[0], source);
    }
  }
  visit(stage, run);
  return selected;
}
export function newestSelection(history: History): Selection {
  const items = stages.flatMap((stage) =>
    history[stage].map((run) => ({ stage, run })),
  );
  items.sort(
    (a, b) =>
      b.run.created_at.localeCompare(a.run.created_at) ||
      stages.indexOf(b.stage) - stages.indexOf(a.stage),
  );
  return items.length
    ? selectHistory(history, items[0].stage, items[0].run)
    : {};
}
