"use client";
import type { Proposition, Segment } from "@/lib/types";
import {
  appendContext,
  contextSuggestions,
  CONTEXT_LIMIT,
} from "@/lib/context-suggestions";
import { timecode } from "@/lib/api";

export default function ContextSuggestions({
  proposition,
  segments,
  value,
  onChange,
}: {
  proposition: Proposition;
  segments: Segment[];
  value: string;
  onChange: (value: string) => void;
}) {
  const suggestions = contextSuggestions(proposition, segments);
  return (
    <div
      className="context-suggestions"
      role="group"
      aria-label="Suggested search context"
    >
      <h5>Suggested search context</h5>
      <p className="small">
        Click to add, then edit above. Quotations may refer to another
        topic—check relevance. Search directions are prompts, not facts or
        evidence.
      </p>
      {suggestions.map((item, index) => {
        const next = appendContext(value, item.text);
        const added = value
          .split("\n")
          .some((line) => line.trim() === item.text.trim());
        return (
          <div className="context-suggestion" key={`${item.origin}-${index}`}>
            <button
              type="button"
              className="secondary"
              disabled={next === value}
              onClick={() => onChange(next)}
              title={
                added
                  ? "Already added; edit or remove it in the text field."
                  : next === value
                    ? "Not enough space; edit the context field first."
                    : "Append to search context"
              }
            >
              {item.text}
              {added ? " · Added" : ""}
            </button>
            <span className="small">
              {item.origin}
              {item.start !== undefined ? ` · ${timecode(item.start)}` : ""}
            </span>
            {item.quote && (
              <details>
                <summary>View original quotation</summary>
                <blockquote>{item.quote}</blockquote>
              </details>
            )}
          </div>
        );
      })}
      {!suggestions.length && (
        <p className="small">
          No safe context suggestions found. Add the missing details manually.
        </p>
      )}
      <p className="small">
        {value.length}/{CONTEXT_LIMIT} characters. If unclear: which person or
        policy, place, date, and measure? Relative dates need the video's
        date—not today's date. Unknown details should stay unknown.
      </p>
    </div>
  );
}
