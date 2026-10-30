import { test, expect, Page } from "@playwright/test";
async function upload(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: /Upload & extract/ }),
  ).toBeDisabled();
  await page
    .getByLabel("Video file")
    .setInputFiles({
      name: "synthetic-browser-test.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("fixture media"),
    });
  await page.getByRole("button", { name: /Upload & extract/ }).click();
  await expect(
    page.getByRole("heading", { name: "Timestamped transcript" }),
  ).toBeVisible();
}
async function toAtoms(page: Page) {
  await upload(page);
  await page
    .getByRole("button", { name: "Transcribe video", exact: true })
    .click();
  await expect(
    page.getByText("In 2024, London opened 2 schools.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Detect check-worthy/ }).click();
  const claims = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", { name: "Check-worthy candidates" }),
    });
  await claims.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Decompose selected claims" }).click();
  await expect(
    page.getByRole("button", { name: /Retrieve evidence/ }),
  ).toBeDisabled();
  const atoms = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", {
        name: "Atomic propositions",
        exact: true,
      }),
    });
  await atoms.getByRole("checkbox").first().check();
}
async function toMapping(page: Page) {
  await toAtoms(page);
  await page.getByRole("button", { name: /Retrieve evidence/ }).click();
  await expect(
    page.getByRole("heading", { name: "Retrieved evidence", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Map selected evidence/ }),
  ).toBeDisabled();
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: /Map selected evidence/ }).click();
  await expect(page.getByText("SUPPORTS", { exact: true })).toBeVisible();
}
async function complete(page: Page) {
  await toMapping(page);
  await page.getByRole("button", { name: /Rank evidence & group/ }).click();
  await page
    .getByRole("button", { name: "Verify selected evidence", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Calculate Evidence Confidence", exact: true })
    .click();
  await expect(
    page.getByText("Evidence Confidence: 50%", { exact: true }),
  ).toBeVisible();
}
test("complete upload-to-confidence workflow, citations, export and reload", async ({
  page,
}) => {
  await complete(page);
  await expect(page.getByText("Supported", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "Evidence adequacy—not the probability that this claim is true.",
    ),
  ).toBeVisible();
  const source = page.getByRole("link", { name: "City report" });
  await expect(source).toHaveAttribute("href", "https://example.org/report");
  await expect(page.locator("blockquote")).toContainText(
    "In 2024, London opened 2 schools.",
  );
  await page
    .getByText("Inspect score components and limits", { exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText(/Maximum 50%: Only one/)).toBeVisible();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download selected run JSON" })
    .click();
  expect((await download).suggestedFilename()).toMatch(
    /^verifistream-.*\.json$/,
  );
  await page.reload();
  await expect(
    page.getByText("Evidence Confidence: 50%", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/findings-desktop.png",
    fullPage: true,
  });
});
test("selecting an earlier stage clears downstream results and history restores exact ancestry", async ({
  page,
}) => {
  await complete(page);
  const oldVerification = await page
    .getByLabel("Verification history")
    .inputValue();
  const confidence = await page.getByLabel("Confidence history").inputValue();
  await page.getByLabel("Verification history").selectOption(oldVerification);
  await expect(
    page.getByText("Evidence Confidence: 50%", { exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Confidence history").selectOption(confidence);
  await expect(
    page.getByText("Evidence Confidence: 50%", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /02\s*Transcript/ }).click();
  const originalTranscript = await page
    .getByLabel("Transcript history")
    .inputValue();
  await page
    .getByRole("button", { name: "Transcribe video", exact: true })
    .click();
  await expect(page.getByLabel("Transcript history")).not.toHaveValue(
    originalTranscript,
  );
  await page.getByRole("button", { name: /05\s*Findings/ }).click();
  await expect(
    page.getByText("Evidence Confidence: 50%", { exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Confidence history").selectOption(confidence);
  await page.getByRole("button", { name: /02\s*Transcript/ }).click();
  await expect(page.getByLabel("Transcript history")).toHaveValue(
    originalTranscript,
  );
});
test("201 failed run is not presented as successful transcription", async ({
  page,
}) => {
  await upload(page);
  await page.route("**/transcriptions", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 201,
      json: {
        id: "failed-run",
        video_id: "fixture",
        created_at: new Date().toISOString(),
        status: "failed",
        result: null,
        text: "",
        error_code: "transcription_timeout",
        error_message: "Transcription timed out.",
      },
    });
  });
  await page
    .getByRole("button", { name: "Transcribe video", exact: true })
    .click();
  await expect(page.locator(".notice[role=alert]")).toContainText(
    "Transcription timed out.",
  );
  await expect(
    page.getByRole("button", { name: /Detect check-worthy/ }),
  ).toHaveCount(0);
});
test("manual URL validation and network failure do not silently retry mutations", async ({
  page,
}) => {
  await toAtoms(page);
  await page.getByLabel("Evidence discovery").selectOption("manual_urls");
  await page.getByLabel("Source URLs 1").fill("http://insecure.example/report");
  await page.getByRole("button", { name: /Retrieve evidence/ }).click();
  await expect(page.locator(".notice[role=alert]")).toContainText("HTTPS");
  await page.getByLabel("Source URLs 1").fill("https://example.org/report");
  let calls = 0;
  await page.route("**/retrievals", async (route) => {
    if (route.request().method() === "POST") {
      calls++;
      await route.abort();
    } else await route.continue();
  });
  await page.getByRole("button", { name: /Retrieve evidence/ }).click();
  await expect(page.locator(".notice[role=alert]")).toContainText("may still be running");
  expect(calls).toBe(1);
  await expect(
    page.getByRole("button", { name: /Retrieve evidence/ }),
  ).toBeEnabled();
});
test("mobile workflow fits viewport and keeps sources and confidence accessible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await complete(page);
  const widths = await page.evaluate(() => ({
    viewport: innerWidth,
    body: document.documentElement.scrollWidth,
  }));
  expect(widths.body).toBeLessThanOrEqual(widths.viewport);
  await expect(page.getByRole("link", { name: "City report" })).toBeVisible();
  await page.screenshot({
    path: "test-results/findings-mobile.png",
    fullPage: true,
  });
});
test("unsafe citation links and source HTML are never executed", async ({
  page,
}) => {
  await complete(page);
  await page.route("**/verifications", async (route) => {
    const response = await route.fetch();
    const runs = await response.json();
    for (const run of runs) {
      for (const p of run.results) {
        for (const c of p.citations) {
          c.url = "javascript:alert(1)";
          c.title = "<img src=x onerror=alert(1)>";
        }
      }
    }
    await route.fulfill({ json: runs });
  });
  // Reopening runs reads exact records rather than trusting cached rendering.
  await page.getByRole("button", { name: "Refresh saved runs" }).click();
  await expect(
    page.getByText("<img src=x onerror=alert(1)> (link unavailable)", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
  await expect(page.locator(".citation img")).toHaveCount(0);
});

test("proposition selection is capped at three", async ({ page }) => {
  await toAtoms(page);
  await page.route("**/decompositions", async (route) => {
    const response = await route.fetch();
    const runs = await response.json();
    const original = runs[0].results[0].propositions[0];
    runs[0].results[0].propositions = Array.from({ length: 4 }, (_, i) => ({
      ...original,
      id: `${original.id.slice(0, -1)}${i}`,
      text: `Synthetic selection-limit proposition ${i + 1}`,
    }));
    await route.fulfill({ json: runs });
  });
  await page.getByRole("button", { name: "Refresh saved runs" }).click();
  const atoms = page
    .locator("section")
    .filter({
      has: page.getByRole("heading", {
        name: "Atomic propositions",
        exact: true,
      }),
    });
  const boxes = atoms.getByRole("checkbox");
  await expect(boxes).toHaveCount(4);
  for (let i = 0; i < 3; i++) await boxes.nth(i).check();
  await expect(boxes.nth(3)).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Retrieve evidence (3/3)" }),
  ).toBeEnabled();
  await boxes.nth(0).uncheck();
  await expect(boxes.nth(3)).toBeEnabled();
});
test("passage selection is capped at twelve", async ({ page }) => {
  await toAtoms(page);
  await page.route("**/retrievals", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const run = await response.json();
    const original = run.results[0].passages[0];
    run.results[0].passages = Array.from({ length: 13 }, (_, i) => ({
      ...original,
      id: `selection-limit-${i}`,
    }));
    await route.fulfill({ json: run });
  });
  await page.getByRole("button", { name: /Retrieve evidence/ }).click();
  const boxes = page.getByRole("checkbox");
  await expect(boxes).toHaveCount(13);
  for (let i = 0; i < 12; i++) await boxes.nth(i).check();
  await expect(boxes.nth(12)).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Map selected evidence (12/12)" }),
  ).toBeEnabled();
});
