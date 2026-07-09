import { rm, mkdir, copyFile, writeFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(root, "..");
const sourceDir = path.join(projectRoot, "frontend");
const outputDir = path.join(projectRoot, "dist");

const apiBase =
  process.env.JETTY_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.PUBLIC_API_BASE_URL ||
  "";

const config = {
  apiBaseUrl: apiBase.replace(/\/+$/, ""),
  appName: process.env.APP_NAME || "Jetty",
  appRegion: process.env.APP_REGION || "Salt Lake City, Utah",
  defaultModelProvider: process.env.MODEL_PROVIDER || "groq",
};

async function copyRecursive(src, dest) {
  const entries = await readdir(src, { withFileTypes: true });
  await mkdir(dest, { recursive: true });

  for (const entry of entries) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyRecursive(from, to);
      continue;
    }
    const info = await stat(from);
    if (info.isFile()) {
      await copyFile(from, to);
    }
  }
}

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await copyRecursive(sourceDir, outputDir);
await writeFile(
  path.join(outputDir, "config.js"),
  `window.JETTY_CONFIG = ${JSON.stringify(config, null, 2)};\n`,
  "utf8",
);

console.log(`Built Jetty frontend to ${outputDir}`);
