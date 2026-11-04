import type { Proposition, Segment } from "./types";

export interface ContextSuggestion {
  text: string;
  origin:
    | "Claim quotation"
    | "Nearby transcript quotation"
    | "Search direction";
  quote?: string;
  start?: number;
}
export const CONTEXT_LIMIT = 300;

/** Local, source-only suggestions. Never resolve a relative date or infer an entity. */
export function contextSuggestions(
  proposition: Proposition,
  segments: Segment[] = [],
): ContextSuggestion[] {
  const suggestions: ContextSuggestion[] = [];
  const add = (item: ContextSuggestion) => {
    if (
      item.text.trim() &&
      item.text.length <= CONTEXT_LIMIT &&
      !suggestions.some((s) => s.text.toLowerCase() === item.text.toLowerCase())
    )
      suggestions.push(item);
  };
  // Dates and relative times are copied verbatim, with the entire source visible.
  const quote = proposition.source_quote;
  const dates =
    quote.match(
      /\b(?:19|20)\d{2}\b|\b(?:this|last|next) (?:year|month|week)\b|\belection day\b/gi,
    ) || [];
  for (const text of dates.slice(0, 3))
    add({ text, origin: "Claim quotation", quote });
  if (quote.length <= CONTEXT_LIMIT)
    add({ text: quote, origin: "Claim quotation", quote });
  // Only the immediately preceding/following segment; never an unrelated run.
  const before = segments
    .filter((s) => s.end <= proposition.start_seconds)
    .at(-1);
  const after = segments.find((s) => s.start >= proposition.end_seconds);
  for (const segment of [before, after]) {
    if (
      segment &&
      segment.text.trim() !== quote.trim() &&
      Math.min(
        Math.abs(segment.end - proposition.start_seconds),
        Math.abs(segment.start - proposition.end_seconds),
      ) <= 30
    )
      add({
        text: segment.text.trim(),
        origin: "Nearby transcript quotation",
        quote: segment.text,
        start: segment.start,
      });
  }
  const text = proposition.text;
  if (/\b(highest|lowest|record|ever|first)\b/i.test(text))
    add({
      text: "Historical data using the same measure and geographic scope",
      origin: "Search direction",
    });
  if (
    proposition.kind === "causal" ||
    /\b(caused|contributed|because|led to|resulted in)\b/i.test(text)
  )
    add({
      text: "Research assessing causation and alternative explanations",
      origin: "Search direction",
    });
  if (/\d/.test(text))
    add({
      text: "Original data, measurement date and methodology",
      origin: "Search direction",
    });
  return suggestions.slice(0, 8);
}

/** Append only; preserve manual edits and never truncate or silently overwrite. */
export function appendContext(current: string, suggestion: string): string {
  if (current.split("\n").some((line) => line.trim() === suggestion.trim()))
    return current;
  const next = current ? `${current}\n${suggestion}` : suggestion;
  return next.length <= CONTEXT_LIMIT ? next : current;
}
