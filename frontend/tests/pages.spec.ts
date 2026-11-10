import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve } from "node:path";
import type { AddressInfo } from "node:net";

test("both Pages entry points play the sample without a backend", async ({page}) => {
  const root = resolve("..");
  execFileSync("bash", ["github-pages/build.sh"], {cwd: root, env: {...process.env, NEXT_PUBLIC_API_BASE_URL: ""}});
  const types: Record<string,string> = {".html":"text/html", ".js":"text/javascript", ".css":"text/css", ".webm":"video/webm", ".vtt":"text/vtt"};
  const server = createServer(async (req,res) => {
    const match = /^\/(branch|artifact)\/([\w./-]*)$/.exec(req.url || "");
    if (!match || match[2].includes("..")) { res.writeHead(404).end(); return; }
    const file = resolve(root, match[1] === "artifact" ? "github-pages/out" : ".", match[2] || "index.html");
    try { const data = await readFile(file); res.writeHead(200,{"Content-Type":types[extname(file)]}).end(data); }
    catch { res.writeHead(404).end(); }
  });
  await new Promise<void>(r => server.listen(0,"127.0.0.1",r));
  try {
    for (const mode of ["branch", "artifact"]) {
      await page.goto(`http://127.0.0.1:${(server.address() as AddressInfo).port}/${mode}/`);
      await expect(page.locator("#results article")).toHaveCount(2);
      await page.locator("video").evaluate(async (el: HTMLVideoElement) => { el.muted = true; await el.play(); });
      await expect.poll(() => page.locator("video").evaluate((el: HTMLVideoElement) => el.currentTime)).toBeGreaterThan(0);
      await page.locator("#file").setInputFiles({name:"invalid.json",mimeType:"application/json",buffer:Buffer.from("{")});
      await expect(page.locator("#status")).toContainText("invalid JSON");
      await page.locator("#sample").click();
      await expect(page.locator("#results article")).toHaveCount(2);
    }
  } finally { server.closeAllConnections(); server.close(); }
});
