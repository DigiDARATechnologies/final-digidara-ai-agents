import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const assetsDir = path.resolve("dist/assets");
const forbidden = [
  "devFakeCamera",
  "DEVELOPMENT SIMULATION",
  "simulated_faces",
  "fake_camera_allowed",
  "ALLOW_FAKE_CAMERA=true",
  "Development simulation only",
];

let files;
try {
  files = await readdir(assetsDir);
} catch {
  console.error("Production assets not found. Run `npm run build` first.");
  process.exit(1);
}

const matches = [];
for (const file of files) {
  const fullPath = path.join(assetsDir, file);
  const contents = await readFile(fullPath);
  for (const marker of forbidden) {
    if (contents.includes(Buffer.from(marker))) matches.push(`${file}: ${marker}`);
  }
}

if (matches.length) {
  console.error("Development fake-camera content leaked into the production bundle:");
  for (const match of matches) console.error(`- ${match}`);
  process.exit(1);
}

console.log(`PASS: searched ${files.length} production asset(s); zero fake-camera markers found.`);
