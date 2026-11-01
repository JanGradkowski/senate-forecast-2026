// Tiny static file server for the repository root, plus the offline stand-ins for the GUI's CDN files.
// The GUI is served unchanged from /gui/; its CDN requests are fulfilled from npm packages in video/.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const VIDEO_DIR = resolve(fileURLToPath(new URL("..", import.meta.url)));
export const REPO_DIR = resolve(VIDEO_DIR, "..");

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json", ".csv": "text/csv", ".png": "image/png",
  ".svg": "image/svg+xml", ".woff2": "font/woff2", ".woff": "font/woff",
};

export function startServer(port = 0) {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const path = normalize(join(REPO_DIR, decodeURIComponent(url.pathname)));
    if (!path.startsWith(REPO_DIR)) { res.writeHead(403).end(); return; }
    try {
      const body = await readFile(path.endsWith("/") ? join(path, "index.html") : path);
      res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream", "cache-control": "no-store" });
      res.end(body);
    } catch {
      res.writeHead(404).end("not found");
    }
  });
  return new Promise((ok) => server.listen(port, "127.0.0.1", () => ok({ server, origin: `http://127.0.0.1:${server.address().port}` })));
}

// CDN URL -> local file (same package versions the GUI pins)
const CDN = [
  [/^https:\/\/cdn\.jsdelivr\.net\/npm\/d3@7\.9\.0\/dist\/d3\.min\.js$/, "node_modules/d3/dist/d3.min.js"],
  [/^https:\/\/cdn\.jsdelivr\.net\/npm\/topojson-client@3\.1\.0\/dist\/topojson-client\.min\.js$/, "node_modules/topojson-client/dist/topojson-client.min.js"],
  [/^https:\/\/cdn\.jsdelivr\.net\/npm\/us-atlas@3\.0\.1\/states-10m\.json$/, "node_modules/us-atlas/states-10m.json"],
  [/^https:\/\/fonts\.googleapis\.com\/css2\?family=Inter/, "lib/inter.css"],
];

/** Route a Playwright context: local server passes through, known CDN files come from disk, the rest is blocked. */
export async function routeOffline(context, origin) {
  await context.route("**/*", async (route) => {
    const u = route.request().url();
    if (u.startsWith(origin)) return route.continue();
    for (const [re, file] of CDN) {
      if (re.test(u)) {
        let body = await readFile(join(VIDEO_DIR, file));
        // the font CSS is fetched as if from fonts.googleapis.com: point its root-relative URLs at the local server
        if (file.endsWith(".css")) body = body.toString().replaceAll("url(/video/", `url(${origin}/video/`);
        return route.fulfill({ status: 200, body, contentType: TYPES[extname(file)], headers: { "access-control-allow-origin": "*" } });
      }
    }
    if (/fonts\.gstatic\.com/.test(u)) return route.abort();
    console.warn(`blocked external request: ${u}`);
    return route.abort();
  });
}
