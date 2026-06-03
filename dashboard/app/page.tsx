import { listRuns } from "@/lib/runs";
import Link from "next/link";

function statusBadge(status: string) {
  return <span className={`badge badge-${status}`}>{status.replace("_", " ")}</span>;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString();
}

export default function DashboardPage() {
  const runs = listRuns();

  return (
    <div className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1>Agentic Go Contributor</h1>
          <p className="text-sm text-muted">AI-powered GitHub issue resolver — review generated patches</p>
        </div>
      </div>

      <div className="card" style={{ background: "#e3f2fd", border: "1px solid #90caf9" }}>
        <p className="text-sm" style={{ margin: 0 }}>
          <strong>How to use:</strong> Run the CLI agent from your terminal, then review patches here.
        </p>
        <pre style={{ margin: "8px 0 0", background: "#bbdefb" }}>
python -m agentic_go_contributor.cli --repo owner/repo --issue 1234
        </pre>
      </div>

      <h2 style={{ marginTop: 32 }}>Recent Runs</h2>

      {runs.length === 0 && (
        <p className="text-sm text-muted">No runs yet. Start one with the CLI command above.</p>
      )}

      {runs.map((run) => (
        <Link
          key={run.run_id}
          href={`/review/${run.run_id}`}
          style={{ textDecoration: "none", color: "inherit", display: "block" }}
        >
          <div className="card" style={{ cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{run.repo_url}</strong>
                <span style={{ marginLeft: 8, color: "#666" }}>#{run.issue_number}</span>
              </div>
              {statusBadge(run.status)}
            </div>
            <div className="text-sm text-muted mt-2">
              Run: {run.run_id} &middot; {formatTime(run.updated_at)}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
