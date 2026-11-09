"use client";
import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
interface Job {
  id: string;
  status: string;
  stage: string;
  created_at: string;
  error_code: string | null;
  outputs: Record<string, string>;
  request: { action: string };
  retry_of: string | null;
}
export default function JobsPanel({
  videoId,
  audioReady,
  onAudioRetry,
  mappingId,
  onRefresh,
}: {
  videoId: string;
  audioReady: boolean;
  onAudioRetry: () => Promise<void>;
  mappingId?: string;
  onRefresh: () => Promise<void>;
}) {
  const [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result = await api<Job[]>(`/videos/${videoId}/jobs`);
        if (!stopped) setJobs(result);
      } catch (e) {
        if (!stopped) setError((e as Error).message);
      } finally {
        if (!stopped) timer = setTimeout(poll, 2000);
      }
    }
    void poll();
    return () => {
      stopped = true;
      active.current = false;
      clearTimeout(timer);
    };
  }, [videoId]);
  async function perform(task: () => Promise<unknown>) {
    setPending(true);
    setError("");
    try {
      await task();
      if (active.current) setJobs(await api<Job[]>(`/videos/${videoId}/jobs`));
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      if (active.current) setPending(false);
    }
  }
  function submit(action: string, input: object) {
    return perform(() =>
      api(`/videos/${videoId}/jobs`, {
        key: crypto.randomUUID(),
        action,
        input,
      }),
    );
  }
  return (
    <section className="panel jobs-panel" aria-label="Background processing">
      <h2>Background processing</h2>
      <p>
        Start work, then leave or refresh this page. The backend continues while
        Docker is running. Analyze pauses for claim review before evidence
        search.
      </p>
      <div className="actions">
        <button
          className="primary"
          disabled={
            !audioReady || pending ||
            jobs.some((j) => ["queued", "running"].includes(j.status))
          }
          onClick={() => void submit("analyze", {})}
        >
          Analyze video in background
        </button>
        <button
          className="secondary"
          disabled={
            pending ||
            !mappingId ||
            jobs.some((j) => ["queued", "running"].includes(j.status))
          }
          onClick={() => void submit("findings", { mapping_run_id: mappingId })}
        >
          Build findings in background
        </button>
        <button
          className="secondary"
          disabled={pending}
          onClick={() => void perform(onRefresh)}
        >
          Open saved results
        </button>
      </div>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {!jobs.length && (
        <p className="small">
          No background jobs yet. Manual stage controls remain available.
        </p>
      )}
      {jobs.map((job) => (
        <article key={job.id} className="job-card">
          <div className="row spread">
            <strong>
              {job.request.action === "extract_audio" ? "Audio extraction" : job.request.action} · {job.status.replaceAll("_", " ")}
            </strong>
            <span>Stage: {job.stage.replaceAll("_", " ")}</span>
          </div>
          <p className="small">
            {Object.keys(job.outputs).length} saved stage(s) ·{" "}
            {new Date(job.created_at).toLocaleString()}
          </p>
          {job.status === "needs_review" && (
            <p>
              Claims are ready. Open saved results to review propositions and
              choose evidence searches.
            </p>
          )}
          {job.error_code && (
            <p className="notice error">
              {job.error_code}. Inspect saved runs before retrying; an
              interrupted provider call may have incurred a charge.
            </p>
          )}
          <div className="actions">
            {job.status === "queued" && (
              <button
                className="secondary"
                disabled={pending}
                onClick={() =>
                  void perform(() =>
                    api(`/videos/${videoId}/jobs/${job.id}/cancel`, {}),
                  )
                }
              >
                Cancel queued job
              </button>
            )}
            {["failed", "interrupted"].includes(job.status) && (
              <button
                className="secondary"
                disabled={pending}
                onClick={() =>
                  void perform(async () => {
                    await api(`/videos/${videoId}/jobs/${job.id}/retry`, {
                      key: crypto.randomUUID(),
                    });
                    if (job.request.action === "extract_audio") await onAudioRetry();
                  })
                }
              >
                Retry unfinished stages
              </button>
            )}
          </div>
        </article>
      ))}
      <p className="small">
        Queued and running jobs prevent video deletion. Running jobs cannot be
        cancelled safely yet. Restarting Docker interrupts an active stage;
        successful checkpoints remain saved. Refresh does not interrupt
        processing.
      </p>
    </section>
  );
}
