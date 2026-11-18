// Renders the SVG art kit to transparent PNGs for Unity (Assets/Resources/Art/...).
// Usage: node tools/art/render_png.mjs           (needs Google Chrome; no npm packages)
import { spawn } from "node:child_process";
import { mkdirSync, readdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SRC = join(ROOT, "backend", "app", "static", "sim", "art");
const DST = join(ROOT, "unity", "Assets", "Resources", "Art");
const JOBS = [["medallions", 512, 512], ["crests", 256, 308], ["icons", 128, 128], ["portraits", 512, 512], ["ui", 400, 720, "stained_glass.svg"], ["ui", 480, 240, "stone.svg"]];
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

const profile = mkdtempSync(join(tmpdir(), "sv-art-"));
const chrome = spawn(CHROME, ["--headless=new", "--remote-debugging-port=9335", `--user-data-dir=${profile}`,
  "--no-first-run", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) { try { targets = await (await fetch("http://127.0.0.1:9335/json")).json(); break; } catch { await sleep(250); } }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const msg = JSON.parse(m.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await send("Page.enable");
await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
let count = 0;
for (const [sub, w, h, only] of JOBS) {
  mkdirSync(join(DST, sub), { recursive: true });
  for (const file of readdirSync(join(SRC, sub)).filter((f) => f.endsWith(".svg") && (!only || f === only))) {
    await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
    const html = `<html><body style="margin:0;background:transparent"><img src="${pathToFileURL(join(SRC, sub, file))}" style="width:${w}px;height:${h}px;display:block"></body></html>`;
    const page = join(profile, "page.html"); writeFileSync(page, html);
    await send("Page.navigate", { url: pathToFileURL(page).href });
    await sleep(350);
    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: w, height: h, scale: 1 } });
    writeFileSync(join(DST, sub, file.replace(".svg", ".png")), Buffer.from(shot.result.data, "base64"));
    count++;
  }
}
console.log(`rendered ${count} PNGs to ${DST}`);
ws.close(); chrome.kill(); process.exit(0);
