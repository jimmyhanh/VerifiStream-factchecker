import { ConfidenceResult, Selection } from "@/lib/types";
import { Badge, SourceLink, Empty } from "./Shared";
import { timecode } from "@/lib/api";
function Score({ result }: { result: ConfidenceResult }) {
  return (
    <div className="score">
      <div className="score-heading">
        <strong>Evidence Confidence: {result.evidence_confidence}%</strong>
        <span className="badge neutral">Experimental · uncalibrated</span>
      </div>
      <p>Evidence adequacy—not the probability that this claim is true.</p>
      <details>
        <summary>Inspect score components and limits</summary>
        <div className="table-scroll">
          <table>
            <caption>Transparent score breakdown</caption>
            <thead>
              <tr>
                <th>Signal</th>
                <th>Points</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.components).map(([name, c]) => (
                <tr key={name}>
                  <th>{name.replaceAll("_", " ")}</th>
                  <td>
                    {c.points.toFixed(1)} / {c.weight}
                  </td>
                  <td>{c.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          Raw score: {result.raw_score.toFixed(1)}. The lowest applicable cap is
          applied.
        </p>
        <ul>
          {result.caps.map((c, i) => (
            <li key={i}>
              Maximum {c.maximum}%: {c.reason}
            </li>
          ))}
        </ul>
        <p>
          Unknown:{" "}
          {Object.keys(result.unknown_signals)
            .map((x) => x.replaceAll("_", " "))
            .join(", ")}
          .
        </p>
        <ul>
          {result.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
export default function Findings({ selected }: { selected: Selection }) {
  const verification = selected.verification;
  if (!verification || verification.status !== "completed")
    return (
      <Empty>
        Run verification after ranking to see an evidence assessment for each
        atomic proposition.
      </Empty>
    );
  const confidence =
    selected.confidence?.status === "completed" &&
    selected.confidence.request.verification_run_id === verification.id
      ? selected.confidence
      : undefined;
  return (
    <>
      <p className="notice">
        Assessments cover selected retrieved evidence. They do not establish
        universal truth. Independent confirmation is unknown.
      </p>
      {!verification.results.length && (
        <Empty>No propositions were assessed in this run.</Empty>
      )}
      {verification.results.map((p) => (
        <article className="finding" key={p.proposition_id}>
          <div className="row spread">
            <span className="eyebrow">
              {timecode(p.start_seconds)}–{timecode(p.end_seconds)} · Atomic
              proposition
            </span>
            <Badge text={p.evidence_status} />
          </div>
          <h3>{p.proposition_text}</h3>
          <p>{p.explanation}</p>
          <div className="coverage">
            <span>
              <strong>{p.coverage.mapped_passages}</strong> mapped
            </span>
            <span>
              <strong>{p.coverage.selected_passages}</strong> selected
            </span>
            <span>
              <strong>{p.coverage.retrieved_passages}</strong> retrieved
            </span>
            <span>
              <strong>{p.coverage.unmapped_passage_ids.length}</strong> outside
              selection
            </span>
            <span>
              <strong>{p.coverage.unresolved_passage_ids.length}</strong>{" "}
              unresolved
            </span>
          </div>
          <p className="small">
            Retrieval: {p.coverage.retrieval_status}; failed fetches:{" "}
            {p.coverage.failed_fetch_count}.
          </p>
          {confidence?.results.find(
            (r) => r.proposition_id === p.proposition_id,
          ) ? (
            <Score
              result={
                confidence.results.find(
                  (r) => r.proposition_id === p.proposition_id,
                )!
              }
            />
          ) : (
            <p className="small">
              Confidence has not been calculated for this verification.
            </p>
          )}
          <h4>Evidence & citations</h4>
          {!p.citations.length && (
            <Empty>
              No decisive evidence is not proof that a claim is false.
            </Empty>
          )}
          {p.citations.map((c) => (
            <div className="citation" key={c.passage_id}>
              <div className="row spread">
                <SourceLink url={c.url}>
                  {c.title || c.publisher || "Source"}
                </SourceLink>
                <Badge text={c.relationship} />
              </div>
              <blockquote>{c.quote}</blockquote>
              <p>{c.mapping_explanation}</p>
              <p className="small">
                {c.publisher || "Publisher unknown"} · Published{" "}
                {c.publication_date || "date unknown"} · {c.source_type} ·{" "}
                {c.primary_secondary}
              </p>
              <details>
                <summary>Source provenance & caveats</summary>
                <p className="small break">{c.url}</p>
                <p>
                  Metadata: {c.metadata_origin}. Dependence group:{" "}
                  <code>{c.group_id}</code>. This group is not a verified
                  independent source.
                </p>
                {c.mapping_caveats.length ? (
                  <ul>
                    {c.mapping_caveats.map((v, i) => (
                      <li key={i}>{v}</li>
                    ))}
                  </ul>
                ) : (
                  <p>
                    No mapping caveats recorded; this does not establish
                    completeness.
                  </p>
                )}
              </details>
            </div>
          ))}
          <details>
            <summary>Assessment limitations</summary>
            <ul>
              {p.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </details>
        </article>
      ))}
    </>
  );
}
