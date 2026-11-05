"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceLink } from "./Shared";
type Rating = {
  provider: string;
  original_label: string;
  category: string | null;
  rating_url: string;
  methodology_url: string;
  assessed_on: string | null;
  retrieved_at: string;
  freshness: string;
};
type Profile = {
  status: string;
  publisher: string | null;
  ratings: Rating[];
  registry_version: string;
  captured_at: string;
  domain_evidence_url: string | null;
};
export default function PublisherRating({
  url,
  snapshotPath,
}: {
  url: string;
  snapshotPath?: string;
}) {
  const [profile, setProfile] = useState<Profile>(),
    [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setProfile(undefined);
    setError("");
    async function load() {
      try {
        let value: Profile | undefined;
        if (snapshotPath) {
          const snapshot = await api<{ sources: Record<string, Profile> }>(
            snapshotPath,
          );
          value = snapshot.sources[url];
          if (!value) throw new Error("No rating snapshot for this citation.");
        } else
          value = await api<Profile>(
            `/publisher-ratings?url=${encodeURIComponent(url)}`,
          );
        if (!cancelled) setProfile(value);
      } catch {
        if (!cancelled)
          setError(
            snapshotPath
              ? "Historical publisher rating unavailable. Current ratings are not substituted."
              : "Publisher ratings unavailable. This does not imply low reliability.",
          );
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [url, snapshotPath]);
  return (
    <div className="publisher-rating">
      <strong>
        Publisher reliability ·{" "}
        {error
          ? "Unavailable"
          : !profile
            ? "Loading…"
            : profile.status === "unrated"
              ? "Unrated"
              : "External ratings"}
      </strong>
      {error && <p className="small">{error}</p>}
      {profile && (
        <>
          <p className="small">
            {snapshotPath ? "Saved with this verification" : "Current registry"}{" "}
            · {profile.registry_version}. Publication-level assessment; not
            proof that this passage is correct.
          </p>
          {!profile.ratings.length && (
            <p className="small">
              No attributed rating supplied. Unrated does not mean unreliable.
            </p>
          )}
          {profile.ratings.map((r) => (
            <article key={r.provider} className="publisher-provider">
              <strong>
                {r.provider}: {r.original_label}
              </strong>
              {r.category && r.category !== r.original_label && (
                <p>Registry category: {r.category}</p>
              )}
              <p className="small">
                Assessed: {r.assessed_on || "Unknown"} · {r.freshness} ·
                Retrieved: {r.retrieved_at}
              </p>
              <SourceLink url={r.rating_url}>Rating source</SourceLink>
              {" · "}
              <SourceLink url={r.methodology_url}>Methodology</SourceLink>
            </article>
          ))}
          <p className="small">
            Providers are not averaged. These ratings do not change Evidence
            Confidence or assign political bias.
          </p>
        </>
      )}
    </div>
  );
}
