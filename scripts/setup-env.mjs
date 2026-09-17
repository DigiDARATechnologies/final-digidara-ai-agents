import { constants, copyFileSync, existsSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const envFiles = [
  ".env",
  "docker/mysql/.env",
  "agents/orchestrator/.env",
  "agents/project_AI_Agent/.env",
  "agents/codeforge_agent/services/lms-api/.env",
  "agents/communication-ai-agent/backend/.env",
  "agents/aptitude_agent/.env",
  "agents/resume_builder_agent/backend/.env",
  "agents/certificate_agent/.env",
  "agents/job_agent/.env",
];

let created = 0;

for (const destinationName of envFiles) {
  const destination = resolve(projectRoot, destinationName);
  const source = destination + ".example";

  if (existsSync(destination)) {
    console.log("kept    " + relative(projectRoot, destination));
    continue;
  }

  if (!existsSync(source)) {
    console.error("missing " + relative(projectRoot, source));
    process.exitCode = 1;
    continue;
  }

  copyFileSync(source, destination, constants.COPYFILE_EXCL);
  created += 1;
  console.log("created " + relative(projectRoot, destination));
}

console.log("\nCreated " + created + " file(s). Existing .env files were not changed.");
console.log("Next: fill the placeholders by following ENV_WORKFLOW.md.");
