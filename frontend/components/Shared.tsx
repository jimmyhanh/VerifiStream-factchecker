import { ReactNode } from "react";
import { AnyRun } from "@/lib/types";
import { safeLink } from "@/lib/api";
export function Badge({ text }: { text: string }) {
  const tone = /contradict|conflict|failed/i.test(text)
    ? "rose"
    : /review|qualif|partial|insufficient|processing/i.test(text)
      ? "amber"
      : /supported|supports|completed|mapped|retrieved/i.test(text)
        ? "teal"
        : "neutral";
  return <span className={`badge ${tone}`}>{text.replaceAll("_", " ")}</span>;
}
export function SourceLink({
  url,
  children,
}: {
  url: string;
  children: ReactNode;
}) {
  const href = safeLink(url);
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children} <span aria-hidden="true">↗</span>
    </a>
  ) : (
    <span>{children} (link unavailable)</span>
  );
}
export function RunHistory({
  label,
  runs,
  selected,
  onSelect,
}: {
  label: string;
  runs: AnyRun[];
  selected?: AnyRun;
  onSelect: (id: string) => void;
}) {
  if (!runs.length) return null;
  return (
    <div className="run-history">
      <label>
        {label} history
        <select
          value={selected?.id || ""}
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="" disabled>
            Select saved run
          </option>
          {runs.map((r, i) => (
            <option key={r.id} value={r.id}>
              {new Date(r.created_at).toLocaleString()} · {r.status} · #
              {runs.length - i}
            </option>
          ))}
        </select>
      </label>
      {selected && <Badge text={selected.status} />}
    </div>
  );
}
export function RunNotice({ run }: { run?: AnyRun }) {
  if (!run) return null;
  return (
    <>
      {run.status === "failed" && (
        <p role="alert" className="notice error">
          This run failed:{" "}
          {run.error_message ||
            run.error_code ||
            "Inspect the passage errors below."}{" "}
          Correct the problem, then explicitly run the step again.
        </p>
      )}
      {run.status === "processing" && (
        <p className="notice">
          This run is still marked processing. Refresh saved runs to check
          again. A server interruption may leave a stale run; automatic recovery
          is not available yet.
        </p>
      )}
      {run.warnings?.length ? (
        <details className="run-warnings">
          <summary>Run notes ({run.warnings.length})</summary>
          <ul>
            {run.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
