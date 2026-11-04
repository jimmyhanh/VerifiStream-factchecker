import type { Source } from "./types";
export type SourceMetadata = Pick<
  Source,
  | "publisher"
  | "publication_date"
  | "source_type"
  | "primary_secondary"
  | "metadata_origin"
>;
/** v1 intentionally abstains: page-declared metadata cannot establish credibility. */
export function sourceAssessment(source: SourceMetadata) {
  const known = (value: string | null) =>
    value?.trim() && value.trim().toLowerCase() !== "unknown"
      ? value
      : "Unknown";
  return {
    version: "source-assessment-v1",
    score: null,
    rating: "Not rated",
    reason:
      "Verified reliability signals are unavailable. Missing information is not proof of an unreliable source.",
    signals: [
      { label: "Publisher", value: known(source.publisher) },
      { label: "Publication date", value: known(source.publication_date) },
      { label: "Source type", value: known(source.source_type) },
      { label: "Primary / secondary", value: known(source.primary_secondary) },
      { label: "Metadata origin", value: known(source.metadata_origin) },
      { label: "Independent confirmation", value: "Not established" },
      { label: "Editorial / research methodology", value: "Not assessed" },
      { label: "Correction history", value: "Not assessed" },
    ],
  };
}
