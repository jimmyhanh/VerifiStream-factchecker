"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AtomicRun, Candidate, ClaimRun } from "@/lib/types";
import { Badge } from "./Shared";
type Item = {
  candidate_id: string;
  text: string;
  kind: "factual" | "observed_outcome" | "causal";
  needs_context: boolean;
  scope_notes: string[];
};
type Draft = {
  id: string;
  status: string;
  request: { claim_run_id: string; candidate_ids: string[] };
  created_at: string;
  results: {
    candidate_id: string;
    source_quote: string;
    status: string;
    propositions: Omit<Item, "candidate_id">[];
    review_reason: string | null;
    error_code: string | null;
  }[];
};
export default function ReviewPanel({
  claim,
  selectedIds,
  targetIds,
  work,
  onApproved,
}: {
  claim: ClaimRun;
  selectedIds: string[];
  targetIds: string[];
  work: (label: string, task: () => Promise<void>) => Promise<void>;
  onApproved: (run: AtomicRun) => void;
}) {
  const [items, setItems] = useState<Item[]>([]),
    [ack, setAck] = useState(false),
    [draft, setDraft] = useState<Draft>();
  const [drafts, setDrafts] = useState<Draft[]>([]),
    [activeIds, setActiveIds] = useState<string[]>([]);
  function manual(ids: string[]) {
    setActiveIds(ids);
    setDraft(undefined);
    setAck(false);
    setItems(
      claim.candidates
        .filter((c) => ids.includes(c.id))
        .map((c) => ({
          candidate_id: c.id,
          text: c.quote.length <= 600 ? c.quote : "",
          kind: "factual",
          needs_context: true,
          scope_notes: [],
        })),
    );
  }
  useEffect(() => {
    if (targetIds.length) manual(targetIds);
  }, [targetIds]);
  function useDraft(run: Draft) {
    setDraft(run);
    setAck(false);
    setActiveIds(run.request.candidate_ids);
    setItems(
      run.results.flatMap((r) =>
        r.propositions.map((p) => ({ ...p, candidate_id: r.candidate_id })),
      ),
    );
  }
  function update(index: number, changes: Partial<Item>) {
    setItems((old) =>
      old.map((p, i) => (i === index ? { ...p, ...changes } : p)),
    );
    setAck(false);
  }
  async function suggest() {
    const run = await api<Draft>(
      `/videos/${claim.video_id}/proposition-drafts`,
      { claim_run_id: claim.id, candidate_ids: selectedIds },
    );
    setDrafts((old) => [run, ...old]);
    useDraft(run);
  }
  async function approve() {
    const run = await api<AtomicRun>(
      `/videos/${claim.video_id}/reviewed-decompositions`,
      {
        claim_run_id: claim.id,
        draft_run_id: draft?.id || null,
        items,
        meaning_preserved: ack,
      },
    );
    onApproved(run);
    setItems([]);
    setAck(false);
    setDraft(undefined);
    setActiveIds([]);
  }
  const sources = claim.candidates.filter((c) => activeIds.includes(c.id));
  return (
    <section className="panel review-panel">
      <span className="eyebrow">Complex statements / Review before search</span>
      <h2>Review propositions</h2>
      <p>
        Automatic splitting can miss conversational claims. Select up to 10
        candidates above, or use “Review this statement” below. Review and
        approve the wording to make it searchable.
      </p>
      <div className="actions">
        <button
          className="secondary"
          disabled={
            !selectedIds.length ||
            selectedIds.length > 10 ||
            claim.status !== "completed"
          }
          onClick={() => manual(selectedIds)}
        >
          Review selected manually
        </button>
        <button
          className="secondary"
          disabled={
            !selectedIds.length ||
            selectedIds.length > 10 ||
            claim.status !== "completed"
          }
          onClick={() =>
            void work("Generating unverified proposition suggestions…", suggest)
          }
        >
          Suggest with AI
        </button>
        <button
          className="secondary"
          onClick={() =>
            void work("Loading saved suggestions…", async () =>
              setDrafts(
                (
                  await api<Draft[]>(
                    `/videos/${claim.video_id}/proposition-drafts`,
                  )
                ).filter((d) => d.request.claim_run_id === claim.id),
              ),
            )
          }
        >
          Load saved drafts
        </button>
      </div>
      <p className="small">
        Manual review needs no AI key. AI suggestions send selected quotations
        to your configured provider and may incur cost. Suggestions are not
        facts and cannot be searched until approved.
      </p>
      {drafts.length > 0 && (
        <label>
          Suggestion history
          <select
            value={draft?.id || ""}
            onChange={(e) => {
              const d = drafts.find((d) => d.id === e.target.value);
              if (d) useDraft(d);
            }}
          >
            <option value="" disabled>
              Choose a saved draft
            </option>
            {drafts.map((d) => (
              <option key={d.id} value={d.id}>
                {new Date(d.created_at).toLocaleString()} · {d.status}
              </option>
            ))}
          </select>
        </label>
      )}
      {draft && (
        <div className="notice">
          <Badge text={draft.status} />
          {draft.results.map((r) => (
            <p key={r.candidate_id}>
              {r.error_code ||
                r.review_reason ||
                "Unverified suggestions ready for your review."}
            </p>
          ))}
          {draft.status === "failed" && (
            <p>
              Check DECOMPOSITION_MODEL (or MAPPING_MODEL) and OPENAI_API_KEY on
              the backend, or use manual review.
            </p>
          )}
        </div>
      )}
      {sources.map((candidate: Candidate) => (
        <div className="review-source" key={candidate.id}>
          <h3>Original transcript statement</h3>
          <blockquote>{candidate.quote}</blockquote>
          <p className="small">
            The original text and timestamps will be retained unchanged.
          </p>
          {items.map((item, index) =>
            item.candidate_id !== candidate.id ? null : (
              <div className="context-fields" key={index}>
                <label>
                  Proposition wording {index + 1}
                  <textarea
                    maxLength={600}
                    value={item.text}
                    onChange={(e) => update(index, { text: e.target.value })}
                  />
                </label>
                <label>
                  Proposition kind {index + 1}
                  <select
                    value={item.kind}
                    onChange={(e) =>
                      update(index, { kind: e.target.value as Item["kind"] })
                    }
                  >
                    <option value="factual">
                      Factual assertion / attributed statement
                    </option>
                    <option value="observed_outcome">Observed outcome</option>
                    <option value="causal">Causal assertion</option>
                  </select>
                </label>
                <label className="row">
                  <input
                    type="checkbox"
                    checked={item.needs_context}
                    onChange={(e) =>
                      update(index, { needs_context: e.target.checked })
                    }
                  />
                  Needs search context (missing entity, place or time)
                </label>
                {item.scope_notes.length > 0 && (
                  <ul className="small">
                    {item.scope_notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                )}
                <button
                  className="text-button"
                  onClick={() => {
                    setItems((old) => old.filter((_, i) => i !== index));
                    setAck(false);
                  }}
                >
                  Remove proposition {index + 1}
                </button>
              </div>
            ),
          )}
          <button
            className="secondary"
            disabled={items.length >= 30}
            onClick={() => {
              setItems((old) => [
                ...old,
                {
                  candidate_id: candidate.id,
                  text: "",
                  kind: "factual",
                  needs_context: true,
                  scope_notes: [],
                },
              ]);
              setAck(false);
            }}
          >
            Add proposition for this statement
          </button>
        </div>
      ))}
      {!!sources.length && (
        <>
          <p className="notice">
            Keep “if”, “may”, promises, who said it, negation, numbers, and
            dates in each applicable proposition. Do not change a conditional
            promise into a payment that happened. Do not repair uncertain
            transcription by guessing.
          </p>
          <label className="review-ack">
            <input
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
            />
            I checked every proposition against the original, preserved its
            conditions, attribution, timing, quantities and meaning, and
            understand approval does not verify its truth.
          </label>
          <button
            className="primary"
            disabled={
              !ack || !items.length || items.some((i) => !i.text.trim())
            }
            onClick={() => void work("Saving reviewed propositions…", approve)}
          >
            Approve & enable search
          </button>
        </>
      )}
    </section>
  );
}
