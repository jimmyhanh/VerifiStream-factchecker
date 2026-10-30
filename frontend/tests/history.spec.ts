import { test, expect } from "@playwright/test";
import { safeLink } from "../lib/api";
import { selectHistory, newestSelection } from "../lib/history";
import { emptyHistory, Runs } from "../lib/types";
test("missing parent fails closed instead of mixing latest runs", () => {
  const history = emptyHistory();
  history.claims = [
    { id: "c", transcript_run_id: "missing" } as Runs["claims"],
  ];
  expect(() => selectHistory(history, "claims", history.claims[0])).toThrow(
    /parent run is missing/,
  );
  expect(newestSelection(emptyHistory())).toEqual({});
});
test("source links only permit HTTP(S) without credentials", () => {
  for (const value of [
    "javascript:alert(1)",
    "data:text/html,x",
    "//example.com",
    "https://user:password@example.com",
    "bad",
  ])
    expect(safeLink(value)).toBeUndefined();
  expect(safeLink("https://example.com/report")).toBe(
    "https://example.com/report",
  );
});
