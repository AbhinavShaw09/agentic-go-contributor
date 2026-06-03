import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(process.cwd(), "..", "data", "runs");

export interface RunStatus {
  run_id: string;
  status: string;
  repo_url: string;
  issue_number: number;
  updated_at: string;
}

export interface Review {
  patch: string;
  plan: string;
  errors: string[];
  created_at: string;
}

export interface Summary {
  repo: string;
  issue: number;
  issue_title: string;
  issue_type: string;
  issue_summary: string;
  relevant_files_count: number;
  relevant_tests_count: number;
  validation_success: boolean;
  validation_attempts: number;
  validation_errors: string[];
  human_approved: boolean;
  human_feedback: string;
  timestamp: string;
}

export function listRuns(limit = 20): RunStatus[] {
  if (!fs.existsSync(DATA_DIR)) return [];
  const dirs = fs
    .readdirSync(DATA_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .sort((a, b) => {
      const sa = readStatus(path.join(DATA_DIR, a.name));
      const sb = readStatus(path.join(DATA_DIR, b.name));
      return (sb?.updated_at || "").localeCompare(sa?.updated_at || "");
    });
  const runs: RunStatus[] = [];
  for (const d of dirs) {
    const status = readStatus(path.join(DATA_DIR, d.name));
    if (status) {
      runs.push({ run_id: d.name, ...status });
    }
    if (runs.length >= limit) break;
  }
  return runs;
}

export function getRun(runId: string): {
  status: RunStatus;
  review: Review | null;
  summary: Summary | null;
} | null {
  const dir = path.join(DATA_DIR, runId);
  if (!fs.existsSync(dir)) return null;
  const status = readStatus(dir);
  if (!status) return null;
  const review = readJSON<Review>(path.join(dir, "review.json"));
  const summary = readJSON<Summary>(path.join(dir, "summary.json"));
  return { status: { run_id: runId, ...status }, review, summary };
}

export function writeDecision(
  runId: string,
  approved: boolean,
  feedback: string
): boolean {
  const dir = path.join(DATA_DIR, runId);
  if (!fs.existsSync(dir)) return false;
  const decision = {
    approved,
    feedback,
    decided_at: new Date().toISOString(),
  };
  fs.writeFileSync(
    path.join(dir, "decision.json"),
    JSON.stringify(decision, null, 2) + "\n"
  );
  // Update status
  const statusPath = path.join(dir, "status.json");
  const current = fs.existsSync(statusPath)
    ? JSON.parse(fs.readFileSync(statusPath, "utf-8"))
    : {};
  current.status = approved ? "approved" : "rejected";
  current.updated_at = new Date().toISOString();
  fs.writeFileSync(statusPath, JSON.stringify(current, null, 2) + "\n");
  return true;
}

function readStatus(dir: string): Omit<RunStatus, "run_id"> | null {
  return readJSON<Omit<RunStatus, "run_id">>(path.join(dir, "status.json"));
}

function readJSON<T>(filepath: string): T | null {
  if (!fs.existsSync(filepath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filepath, "utf-8")) as T;
  } catch {
    return null;
  }
}
