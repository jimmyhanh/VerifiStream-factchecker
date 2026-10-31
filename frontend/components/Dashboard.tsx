"use client";
import { useEffect, useRef, useState } from "react";
import { api, timecode } from "@/lib/api";
import {
  AnyRun,
  Configuration,
  History,
  Runs,
  Selection,
  Stage,
  Video,
  emptyHistory,
  endpoints,
  stages,
} from "@/lib/types";
import { newestSelection, selectHistory } from "@/lib/history";
import { Badge, Empty, RunHistory, RunNotice, SourceLink } from "./Shared";
import Findings from "./Findings";
const tabs = ["Upload", "Transcript", "Claims", "Evidence", "Findings"];
const stageTab: Record<Stage, number> = {
  transcript: 1,
  claims: 2,
  atoms: 2,
  retrieval: 3,
  mapping: 3,
  ranking: 4,
  verification: 4,
  confidence: 4,
};
export default function Dashboard() {
  const [videos, setVideos] = useState<Video[]>([]),
    [video, setVideo] = useState<Video>();
  const [more, setMore] = useState(false),
    [config, setConfig] = useState<Configuration>();
  const [history, setHistory] = useState<History>(emptyHistory),
    [selected, setSelected] = useState<Selection>({});
  const [tab, setTab] = useState(0),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [file, setFile] = useState<File>(),
    [candidateIds, setCandidateIds] = useState<string[]>([]);
  const [propositionIds, setPropositionIds] = useState<string[]>([]),
    [passageIds, setPassageIds] = useState<string[]>([]);
  const [contexts, setContexts] = useState<Record<string, string>>({}),
    [urls, setUrls] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"search" | "manual_urls">("search");
  const locked = useRef(false);
  const propositions =
    selected.atoms?.results.flatMap((r) => r.propositions) || [];
  const sources = selected.retrieval?.sources || [];
  async function work(label: string, task: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    setBusy(label);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Operation failed. Refresh saved runs before retrying.",
      );
    } finally {
      locked.current = false;
      setBusy("");
    }
  }
  function clearChoices() {
    setCandidateIds([]);
    setPropositionIds([]);
    setPassageIds([]);
    setContexts({});
    setUrls({});
  }
  async function library(append = false) {
    const page = await api<Video[]>(
      `/videos?limit=20&offset=${append ? videos.length : 0}`,
    );
    setVideos((old) =>
      append
        ? [...old, ...page.filter((v) => !old.some((o) => o.id === v.id))]
        : page,
    );
    setMore(page.length === 20);
  }
  async function open(item: Video) {
    setVideo(item);
    setSelected({});
    setHistory(emptyHistory());
    clearChoices();
    window.history.replaceState(
      null,
      "",
      `?video=${encodeURIComponent(item.id)}`,
    );
    const data = await Promise.all(
      stages.map(
        async (stage) =>
          [
            stage,
            await api<AnyRun[]>(`/videos/${item.id}/${endpoints[stage]}`),
          ] as const,
      ),
    );
    const loaded = Object.fromEntries(data) as History;
    setHistory(loaded);
    const restored = newestSelection(loaded);
    setSelected(restored);
    const deepest = stages.filter((s) => restored[s]).at(-1);
    setTab(deepest ? stageTab[deepest] : 1);
  }
  useEffect(() => {
    void work("Loading your workspace…", async () => {
      await library();
      setConfig(await api<Configuration>("/configuration"));
      const id = new URLSearchParams(window.location.search).get("video");
      if (id) await open(await api<Video>(`/videos/${encodeURIComponent(id)}`));
    });
  }, []);
  function choose(stage: Stage, id: string) {
    const run = history[stage].find((r) => r.id === id);
    if (!run) return;
    try {
      setSelected(selectHistory(history, stage, run));
      clearChoices();
      setError("");
    } catch (e) {
      setSelected({});
      setError((e as Error).message);
    }
  }
  async function create<K extends Stage>(stage: K, body: object) {
    if (!video) throw new Error("Choose a video first.");
    const run = await api<Runs[K]>(
      `/videos/${video.id}/${endpoints[stage]}`,
      body,
    );
    const next = { ...history, [stage]: [run, ...history[stage]] } as History;
    setHistory(next);
    setSelected(selectHistory(next, stage, run));
    clearChoices();
    setTab(stageTab[stage]);
    setMessage(
      run.status === "failed"
        ? "Run saved with errors. Inspect its details before trying again."
        : run.status === "partial"
          ? "Run saved with partial results. Inspect unresolved passages."
          : "Run saved. Review the results before continuing.",
    );
  }
  function runControl(stage: Stage, label: string) {
    return (
      <>
        <RunHistory
          label={label}
          runs={history[stage]}
          selected={selected[stage]}
          onSelect={(id) => choose(stage, id)}
        />
        <RunNotice run={selected[stage]} />
      </>
    );
  }
  function toggle(
    id: string,
    values: string[],
    set: (v: string[]) => void,
    max: number,
  ) {
    if (values.includes(id)) set(values.filter((v) => v !== id));
    else if (values.length < max) set([...values, id]);
  }
  async function upload() {
    if (!file) throw new Error("Choose a video file.");
    if (!/\.(mp4|mov|webm|mkv)$/i.test(file.name))
      throw new Error("Choose an MP4, MOV, WebM or MKV video.");
    if (!file.size || (config && file.size > config.max_video_bytes))
      throw new Error(
        "The file is empty or exceeds the configured upload limit.",
      );
    const form = new FormData();
    form.append("file", file);
    const created = await api<Video>("/videos", form);
    await library();
    await open(created);
    setFile(undefined);
    setMessage(
      created.status === "completed"
        ? "Video uploaded and audio extracted. You can now transcribe it."
        : "Upload saved, but extraction did not complete. Inspect the error below.",
    );
  }
  async function retrieve() {
    const input: {
      decomposition_run_id?: string;
      proposition_ids: string[];
      mode: string;
      contexts: Record<string, string>;
      source_urls?: Record<string, string[]>;
    } = {
      decomposition_run_id: selected.atoms?.id,
      proposition_ids: propositionIds,
      mode,
      contexts: {},
    };
    for (const id of propositionIds) {
      const context = contexts[id]?.trim();
      if (context) input.contexts[id] = context;
      if (propositions.find((p) => p.id === id)?.needs_context && !context)
        throw new Error(
          "Add search context for each selected proposition that needs it.",
        );
      if (mode === "manual_urls") {
        const list = (urls[id] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean);
        if (list.length < 1 || list.length > 5)
          throw new Error(
            "Enter 1–5 public HTTPS source URLs for each selected proposition.",
          );
        for (const value of list) {
          let parsed: URL;
          try {
            parsed = new URL(value);
          } catch {
            throw new Error("A source URL is invalid.");
          }
          if (
            parsed.protocol !== "https:" ||
            parsed.username ||
            parsed.password
          )
            throw new Error("Source URLs must use HTTPS without credentials.");
        }
        input.source_urls ??= {};
        input.source_urls[id] = list;
      }
    }
    await create("retrieval", input);
  }
  function download() {
    const run = stages
      .map((s) => selected[s])
      .filter(Boolean)
      .at(-1);
    if (!run) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(run, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `verifistream-${run.id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="VerifiStream home">
          <span className="brand-icon">
            V<span>✓</span>
          </span>
          <span>
            VerifiStream<small>EVIDENCE WORKSPACE</small>
          </span>
        </a>
        <div className="sidebar-intro">
          <span className="eyebrow">Your library</span>
          <h2>
            Start with a source.
            <br />
            Follow the evidence.
          </h2>
        </div>
        <button
          className="new-video"
          disabled={!!busy}
          onClick={() => {
            setTab(0);
            setError("");
          }}
        >
          ＋ Upload video
        </button>
        <div className="row spread library-label">
          <span>Saved videos</span>
          <button
            className="text-button"
            disabled={!!busy}
            onClick={() => void work("Refreshing library…", () => library())}
          >
            Refresh
          </button>
        </div>
        <div className="video-list">
          {videos.map((v) => (
            <button
              key={v.id}
              disabled={!!busy}
              className={`video-item ${video?.id === v.id ? "active" : ""}`}
              onClick={() => void work("Opening saved video…", () => open(v))}
            >
              <span className="video-symbol" aria-hidden="true">
                ▷
              </span>
              <span>
                <strong>{v.original_filename}</strong>
                <small>
                  {timecode(v.duration_seconds)} ·{" "}
                  {new Date(v.created_at).toLocaleDateString()} · {v.status}
                </small>
              </span>
            </button>
          ))}
          {!videos.length && (
            <p className="sidebar-empty">
              Your uploaded videos will appear here.
            </p>
          )}
        </div>
        {more && (
          <button
            className="text-button"
            disabled={!!busy}
            onClick={() =>
              void work("Loading more videos…", () => library(true))
            }
          >
            Load more videos
          </button>
        )}
        <div className="sidebar-footer">
          <span className="live-dot" /> Uploaded-video workflow
          <small>Live checking is planned for a later milestone.</small>
        </div>
      </aside>
      <main id="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Research workspace</span>
            <h1>
              {tab === 0
                ? "Make every claim inspectable."
                : video?.original_filename || "Your evidence workspace"}
            </h1>
          </div>
          <div className="row">
            <span className="local-label">LOCAL DEVELOPMENT</span>
            {video && (
              <button
                className="secondary"
                disabled={!!busy}
                onClick={() =>
                  void work("Refreshing saved runs…", async () =>
                    open(await api<Video>(`/videos/${video.id}`)),
                  )
                }
              >
                Refresh saved runs
              </button>
            )}
          </div>
        </header>
        <nav className="steps" aria-label="Workflow">
          {tabs.map((name, i) => (
            <button
              key={name}
              aria-current={tab === i ? "step" : undefined}
              disabled={!!busy || (i > 0 && !video)}
              onClick={() => setTab(i)}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              {name}
            </button>
          ))}
        </nav>
        <div className="feedback" aria-live="polite">
          {busy && (
            <p className="notice pending">
              <span className="spinner" />
              {busy} Keep this page open. Processing may take several minutes.
            </p>
          )}
          {message && <p className="notice">{message}</p>}
        </div>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        {video?.status === "failed" && tab !== 0 && (
          <p className="notice error" role="alert">
            Audio extraction failed: {video.error_message || video.error_code}.
            Upload a corrected video to continue.
          </p>
        )}
        <fieldset className="workspace-fields" disabled={!!busy}>
          {tab === 0 && (
            <section className="upload-layout">
              <div className="panel upload-panel">
                <span className="eyebrow">01 / Bring your own video</span>
                <h2>
                  A clearer view of
                  <br />
                  what was said.
                </h2>
                <p>
                  Upload a video, find factual claims, and inspect the sources
                  behind each assessment.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void work("Uploading video and extracting audio…", upload);
                  }}
                >
                  <label className="upload-zone">
                    <span className="upload-symbol" aria-hidden="true">
                      ↥
                    </span>
                    <strong>Choose a video file</strong>
                    <span>MP4, MOV, WebM or MKV</span>
                    <input
                      aria-label="Video file"
                      type="file"
                      accept=".mp4,.mov,.webm,.mkv"
                      onChange={(e) => setFile(e.target.files?.[0])}
                    />
                  </label>
                  {file && (
                    <p className="small">
                      Selected: {file.name} · {(file.size / 1048576).toFixed(1)}{" "}
                      MiB
                    </p>
                  )}
                  <p className="small">
                    {config
                      ? `Up to ${Math.round(config.max_video_bytes / 1048576)} MiB and ${Math.floor(config.max_duration_seconds / 60)} minutes. `
                      : "Limits are checked by the backend. "}
                    Start with a short English clip for the best demo
                    experience.
                  </p>
                  <button className="primary" disabled={!file}>
                    Upload & extract audio <span aria-hidden="true">→</span>
                  </button>
                </form>
              </div>
              <div className="principles">
                <span className="eyebrow">Built for evidence transparency</span>
                <h2>
                  See the source.
                  <br />
                  Keep your perspective.
                </h2>
                <div>
                  <b>01</b>
                  <h3>One proposition at a time</h3>
                  <p>
                    Separate quantities, outcomes and causal claims before
                    checking them.
                  </p>
                </div>
                <div>
                  <b>02</b>
                  <h3>Evidence you can inspect</h3>
                  <p>
                    Read relevant quotations and see where sources agree,
                    qualify or disagree.
                  </p>
                </div>
                <div>
                  <b>03</b>
                  <h3>Uncertainty stays visible</h3>
                  <p>
                    No political bias scores. Confidence describes evidence, not
                    a probability of truth.
                  </p>
                </div>
              </div>
            </section>
          )}
          {tab === 1 && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">02 / Speech to text</span>
                  <h2>Timestamped transcript</h2>
                  <p>
                    Review what was transcribed before extracting factual
                    claims.
                  </p>
                </div>
                <button
                  className="primary"
                  disabled={video?.status !== "completed"}
                  onClick={() =>
                    void work("Transcribing audio…", () =>
                      create("transcript", {}),
                    )
                  }
                >
                  Transcribe video
                </button>
              </div>
              {runControl("transcript", "Transcript")}
              {selected.transcript?.result ? (
                <>
                  <div className="transcript">
                    {selected.transcript.result.segments.map((s) => (
                      <div className="segment" key={s.id}>
                        <span className="time">
                          {timecode(s.start)}–{timecode(s.end)}
                        </span>
                        <p>{s.text}</p>
                      </div>
                    ))}
                  </div>
                  {!selected.transcript.result.segments.length && (
                    <Empty>No speech segments were detected.</Empty>
                  )}
                  <div className="actions">
                    <button
                      className="primary"
                      disabled={selected.transcript.status !== "completed"}
                      onClick={() =>
                        void work("Detecting check-worthy claims…", () =>
                          create("claims", {
                            transcript_run_id: selected.transcript!.id,
                          }),
                        )
                      }
                    >
                      Detect check-worthy claims →
                    </button>
                    <span className="small">
                      English heuristic baseline; review its selections.
                    </span>
                  </div>
                </>
              ) : (
                <Empty>
                  Transcribe this video to see its speech with timestamps.
                </Empty>
              )}
            </section>
          )}
          {tab === 2 && (
            <>
              <section className="panel">
                <span className="eyebrow">03 / Review & decompose</span>
                <h2>Check-worthy candidates</h2>
                <p>
                  Select the factual statements you want to inspect. These are
                  candidates, not verified facts.
                </p>
                {runControl("claims", "Claim extraction")}
                {selected.claims?.candidates.length ? (
                  <>
                    <p className="selection-count">
                      {candidateIds.length} / 100 candidates selected
                    </p>
                    {selected.claims.candidates.map((c) => (
                      <label className="select-card" key={c.id}>
                        <input
                          type="checkbox"
                          checked={candidateIds.includes(c.id)}
                          disabled={
                            !candidateIds.includes(c.id) &&
                            candidateIds.length >= 100
                          }
                          onChange={() =>
                            toggle(c.id, candidateIds, setCandidateIds, 100)
                          }
                        />
                        <span>
                          <span className="time">
                            {timecode(c.start_seconds)}–
                            {timecode(c.end_seconds)}
                          </span>
                          <strong>{c.quote}</strong>
                          <small>
                            {c.reason}
                            {c.needs_context ? " · Needs context" : ""}
                          </small>
                        </span>
                      </label>
                    ))}
                    <div className="actions">
                      <button
                        className="primary"
                        disabled={
                          !candidateIds.length ||
                          selected.claims.status !== "completed"
                        }
                        onClick={() =>
                          void work("Separating atomic propositions…", () =>
                            create("atoms", {
                              claim_run_id: selected.claims!.id,
                              candidate_ids: candidateIds,
                            }),
                          )
                        }
                      >
                        Decompose selected claims
                      </button>
                    </div>
                  </>
                ) : (
                  <Empty>
                    {selected.claims
                      ? "No candidates were found. Review the transcript; the English heuristic may miss factual statements."
                      : "First detect candidates from a completed transcript."}
                  </Empty>
                )}
              </section>
              <section className="panel">
                <h2>Atomic propositions</h2>
                {runControl("atoms", "Decomposition")}
                {selected.atoms?.results.map((r) => (
                  <div className="atomic-parent" key={r.parent_candidate_id}>
                    <p className="small">Original: {r.source_quote}</p>
                    {r.status === "needs_review" && (
                      <p className="notice">
                        <Badge text="needs_review" /> {r.review_reason}
                      </p>
                    )}
                    {r.propositions.map((p) => (
                      <label className="select-card" key={p.id}>
                        <input
                          type="checkbox"
                          checked={propositionIds.includes(p.id)}
                          disabled={
                            !propositionIds.includes(p.id) &&
                            propositionIds.length >= 3
                          }
                          onChange={() =>
                            toggle(p.id, propositionIds, setPropositionIds, 3)
                          }
                        />
                        <span>
                          <strong>{p.text}</strong>
                          <small>
                            {p.kind.replaceAll("_", " ")} ·{" "}
                            {timecode(p.start_seconds)}–
                            {timecode(p.end_seconds)}
                            {p.needs_context
                              ? " · Search context required"
                              : ""}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                ))}
                {!propositions.length && (
                  <Empty>
                    Decompose selected candidates to identify individual
                    propositions. Ambiguous statements may need review.
                  </Empty>
                )}
                {!!propositions.length && (
                  <>
                    <div className="retrieval-options">
                      <label>
                        Evidence discovery
                        <select
                          value={mode}
                          onChange={(e) =>
                            setMode(e.target.value as typeof mode)
                          }
                        >
                          <option value="search">Brave web search</option>
                          <option value="manual_urls">My source URLs</option>
                        </select>
                      </label>
                      <p className="small">
                        Select 1–3 propositions. Search uses your backend Brave
                        key; manual URLs do not require it.
                      </p>
                    </div>
                    {propositions
                      .filter((p) => propositionIds.includes(p.id))
                      .map((p, i) => (
                        <div className="context-fields" key={p.id}>
                          <h4>{p.text}</h4>
                          <label>
                            Search context {i + 1}{" "}
                            {p.needs_context ? "(required)" : "(optional)"}
                            <textarea
                              maxLength={300}
                              value={contexts[p.id] || ""}
                              onChange={(e) =>
                                setContexts({
                                  ...contexts,
                                  [p.id]: e.target.value,
                                })
                              }
                              placeholder="Identify missing policy, place or time period."
                            />
                          </label>
                          <p className="small">
                            Your context is unverified and does not change the
                            original proposition.
                          </p>
                          {mode === "manual_urls" && (
                            <label>
                              Source URLs {i + 1}
                              <textarea
                                value={urls[p.id] || ""}
                                onChange={(e) =>
                                  setUrls({ ...urls, [p.id]: e.target.value })
                                }
                                placeholder="1–5 public HTTPS URLs, one per line"
                              />
                            </label>
                          )}
                        </div>
                      ))}
                    <div className="actions">
                      <button
                        className="primary"
                        disabled={
                          !propositionIds.length ||
                          selected.atoms?.status !== "completed"
                        }
                        onClick={() =>
                          void work("Retrieving evidence passages…", retrieve)
                        }
                      >
                        Retrieve evidence ({propositionIds.length}/3)
                      </button>
                    </div>
                  </>
                )}
              </section>
            </>
          )}
          {tab === 3 && (
            <>
              <section className="panel">
                <span className="eyebrow">04 / Read before assessing</span>
                <h2>Retrieved evidence</h2>
                <p>
                  Choose relevant passages to map. Retrieval alone does not
                  establish support.
                </p>
                {runControl("retrieval", "Retrieval")}
                {selected.retrieval?.results.map((r) => (
                  <div className="retrieval-result" key={r.proposition_id}>
                    <div className="row spread">
                      <h3>
                        {propositions.find((p) => p.id === r.proposition_id)
                          ?.text || r.query}
                      </h3>
                      <Badge text={r.status} />
                    </div>
                    {r.user_context && (
                      <p className="small">
                        Unverified search context: {r.user_context}
                      </p>
                    )}
                    {r.error_code && (
                      <p className="notice error">{r.error_code}</p>
                    )}
                    {r.attempts
                      .filter((a) => a.status === "failed")
                      .map((a, i) => (
                        <p className="small" key={i}>
                          Fetch failed: {a.error_code} —{" "}
                          <SourceLink url={a.url}>source</SourceLink>
                        </p>
                      ))}
                    {!r.passages.length && (
                      <Empty>
                        No usable passages. Add context or try another source;
                        this does not mean the claim is false.
                      </Empty>
                    )}
                    {r.passages.map((p) => {
                      const source = sources.find((s) => s.id === p.source_id);
                      return (
                        <div className="passage-card" key={p.id}>
                          <label className="select-card">
                            <input
                              type="checkbox"
                              aria-label={`Select passage ${p.id}`}
                              checked={passageIds.includes(p.id)}
                              disabled={
                                !passageIds.includes(p.id) &&
                                passageIds.length >= 12
                              }
                              onChange={() =>
                                toggle(p.id, passageIds, setPassageIds, 12)
                              }
                            />
                            <span>
                              <small>
                                {source?.publisher || "Publisher unknown"} ·{" "}
                                {source?.publication_date || "Date unknown"}
                              </small>
                              <strong>
                                {source?.title || "Retrieved passage"}
                              </strong>
                              <span className="passage-text">{p.text}</span>
                            </span>
                          </label>
                          {source && (
                            <div className="passage-meta">
                              <SourceLink url={source.final_url}>
                                Open source
                              </SourceLink>
                              <span>
                                {source.source_type} ·{" "}
                                {source.primary_secondary} · Metadata unverified
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
                {!selected.retrieval && (
                  <Empty>
                    Select atomic propositions in Claims, then retrieve their
                    evidence.
                  </Empty>
                )}
                <div className="actions">
                  <button
                    className="primary"
                    disabled={
                      !passageIds.length ||
                      selected.retrieval?.status !== "completed"
                    }
                    onClick={() =>
                      void work(
                        "Mapping selected passages to propositions…",
                        () =>
                          create("mapping", {
                            retrieval_run_id: selected.retrieval!.id,
                            passage_ids: passageIds,
                          }),
                      )
                    }
                  >
                    Map selected evidence ({passageIds.length}/12)
                  </button>
                  <span className="small">
                    Sends selected passages and claims to your configured AI
                    provider; charges may apply.
                  </span>
                </div>
              </section>
              <section className="panel">
                <h2>Evidence relationships</h2>
                {runControl("mapping", "Mapping")}
                {selected.mapping?.results.map((r) => (
                  <article className="citation" key={r.passage_id}>
                    <div className="row spread">
                      <strong>
                        {propositions.find((p) => p.id === r.proposition_id)
                          ?.text || "Atomic proposition"}
                      </strong>
                      <Badge text={r.decision?.relationship || r.status} />
                    </div>
                    {r.decision?.evidence_quote && (
                      <blockquote>{r.decision.evidence_quote}</blockquote>
                    )}
                    <p>
                      {r.decision?.explanation ||
                        r.error_code ||
                        "No relationship assigned."}
                    </p>
                    {r.decision?.caveats.map((c, i) => (
                      <p className="small" key={i}>
                        {c}
                      </p>
                    ))}
                    <SourceLink url={r.citation_url}>Inspect source</SourceLink>
                  </article>
                ))}
                {!selected.mapping && (
                  <Empty>
                    Select passages and map them to see support, contradiction,
                    qualification or context.
                  </Empty>
                )}
                <div className="actions">
                  <button
                    className="primary"
                    disabled={
                      !selected.mapping ||
                      !["completed", "partial"].includes(
                        selected.mapping.status,
                      )
                    }
                    onClick={() =>
                      void work(
                        "Ranking evidence and grouping suspected copies…",
                        () =>
                          create("ranking", {
                            mapping_run_id: selected.mapping!.id,
                          }),
                      )
                    }
                  >
                    Rank evidence & group sources →
                  </button>
                </div>
              </section>
            </>
          )}
          {tab === 4 && (
            <>
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">05 / Inspect the assessment</span>
                    <h2>Evidence, not a black box.</h2>
                    <p>
                      Keep uncertainty and disagreements alongside the result.
                    </p>
                  </div>
                  <button
                    className="secondary"
                    disabled={!stages.some((s) => selected[s])}
                    onClick={download}
                  >
                    Download selected run JSON
                  </button>
                </div>
                {runControl("ranking", "Ranking")}
                {selected.ranking && (
                  <details>
                    <summary>Source dependence & ranked passages</summary>
                    <p>
                      Groups indicate detected or suspected dependence.
                      Different groups are not proven independent.
                    </p>
                    {selected.ranking.groups.map((g, i) => (
                      <div className="group" key={g.id}>
                        <strong>
                          Group {i + 1}: {g.source_ids.length} source(s)
                        </strong>
                        <p>{g.independence.replaceAll("_", " ")}</p>
                        <p className="small break">{g.id}</p>
                        {g.links.map((l, j) => (
                          <p className="small" key={j}>
                            {l.reason.replaceAll("_", " ")} · {l.provenance}
                          </p>
                        ))}
                      </div>
                    ))}
                    {selected.ranking.results.map((r) => (
                      <div key={r.proposition_id}>
                        {r.ranked.map((p) => (
                          <p className="small" key={p.passage_id}>
                            Rank {p.rank} · {p.relationship} · Directness:{" "}
                            {p.directness} · Source role: {p.source_role}
                          </p>
                        ))}
                      </div>
                    ))}
                  </details>
                )}
                <div className="actions">
                  <button
                    className="primary"
                    disabled={selected.ranking?.status !== "completed"}
                    onClick={() =>
                      void work("Assessing selected evidence…", () =>
                        create("verification", {
                          ranking_run_id: selected.ranking!.id,
                        }),
                      )
                    }
                  >
                    Verify selected evidence
                  </button>
                  <button
                    className="secondary"
                    disabled={selected.verification?.status !== "completed"}
                    onClick={() =>
                      void work(
                        "Calculating experimental Evidence Confidence…",
                        () =>
                          create("confidence", {
                            verification_run_id: selected.verification!.id,
                          }),
                      )
                    }
                  >
                    Calculate Evidence Confidence
                  </button>
                </div>
                {runControl("verification", "Verification")}
                {runControl("confidence", "Confidence")}
                {selected.verification && (
                  <p className="small">
                    Policy: {selected.verification.policy_version}
                    {selected.confidence
                      ? ` · Confidence algorithm: ${selected.confidence.algorithm_version}`
                      : ""}
                  </p>
                )}
              </section>
              <Findings selected={selected} />
            </>
          )}
        </fieldset>
        <footer className="main-footer">
          <span>VerifiStream / Evidence transparency first</span>
          <span>
            Inspect sources. Understand uncertainty. Reach your own conclusions.
          </span>
        </footer>
      </main>
    </div>
  );
}
