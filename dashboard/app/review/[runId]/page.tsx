"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";

interface RunData {
  status: {
    run_id: string;
    status: string;
    repo_url: string;
    issue_number: number;
    updated_at: string;
  };
  review: {
    patch: string;
    plan: string;
    errors: string[];
    created_at: string;
  } | null;
  summary: {
    validation_success: boolean;
    validation_attempts: number;
    human_approved: boolean;
    human_feedback: string;
  } | null;
}

type ReviewStatus = "loading" | "not_found" | "ready";

export default function ReviewPage() {
  const params = useParams();
  const runId = params.runId as string;

  const [data, setData] = useState<RunData | null>(null);
  const [pageStatus, setPageStatus] = useState<ReviewStatus>("loading");
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchRun = useCallback(async () => {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      if (!res.ok) {
        setPageStatus("not_found");
        return;
      }
      const d: RunData = await res.json();
      setData(d);
      setPageStatus("ready");
    } catch {
      setPageStatus("not_found");
    }
  }, [runId]);

  useEffect(() => {
    fetchRun();
    const interval = setInterval(fetchRun, 5000);
    return () => clearInterval(interval);
  }, [fetchRun]);

  const needsReview = data?.status?.status === "pending_review";
  const isFinal =
    data?.status?.status === "completed" ||
    data?.status?.status === "approved" ||
    data?.status?.status === "rejected";

  const handleApprove = async () => {
    setSubmitting(true);
      await fetch(`/api/runs/${runId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved: true, feedback: "" }),
    });
    await fetchRun();
    setSubmitting(false);
  };

  const handleReject = async () => {
    setSubmitting(true);
      await fetch(`/api/runs/${runId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved: false, feedback }),
    });
    await fetchRun();
    setSubmitting(false);
  };

  if (pageStatus === "loading") {
    return (
      <div className="container">
        <p className="text-sm text-muted">Loading...</p>
      </div>
    );
  }

  if (pageStatus === "not_found" || !data) {
    return (
      <div className="container">
        <h1>Run not found</h1>
        <p className="text-sm text-muted">
          No run with ID <code>{runId}</code> was found.
        </p>
        <a href="/" className="btn btn-primary" style={{ marginTop: 16 }}>
          Back to Dashboard
        </a>
      </div>
    );
  }

  const { status, review, summary } = data;

  function statusBadge(s: string) {
    return (
      <span className={`badge badge-${s}`}>
        {s.replace("_", " ")}
      </span>
    );
  }

  if (isFinal) {
    const approved = summary?.human_approved ?? data?.status?.status === "approved";
    return (
      <div className="container">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1>
            {status.repo_url} #{status.issue_number}
          </h1>
          {statusBadge(status.status)}
        </div>
        <p className="text-sm text-muted">Run: {runId}</p>

        <div className="card" style={{ marginTop: 24 }}>
          <h2>Result</h2>
          {approved ? (
            <p className="text-success" style={{ fontWeight: 500 }}>
              ✅ Patch approved
            </p>
          ) : (
            <p className="text-error" style={{ fontWeight: 500 }}>
              ❌ Patch rejected{summary?.human_feedback ? `: ${summary.human_feedback}` : ""}
            </p>
          )}
          <p className="text-sm text-muted">
            Validation: {summary?.validation_success ? "passed" : "failed"} (
            {summary?.validation_attempts} attempt
            {summary?.validation_attempts !== 1 ? "s" : ""})
          </p>
        </div>

        {review?.patch && (
          <div className="card">
            <h2>Patch</h2>
            <pre>{review.patch}</pre>
          </div>
        )}
        {review?.plan && (
          <div className="card">
            <h2>Plan</h2>
            <pre>{review.plan}</pre>
          </div>
        )}
        {review?.errors && review.errors.length > 0 && (
          <div className="card">
            <h2>Validation Errors</h2>
            <pre>{review.errors.join("\n\n")}</pre>
          </div>
        )}

        <a href="/" className="btn btn-primary">
          Back to Dashboard
        </a>
      </div>
    );
  }

  return (
    <div className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>
          {status.repo_url} #{status.issue_number}
        </h1>
        {statusBadge(status.status)}
      </div>
      <p className="text-sm text-muted">Run: {runId}</p>

      {needsReview && (
        <div
          className="card"
          style={{
            background: "#fff3e0",
            border: "1px solid #ffcc80",
            marginTop: 16,
          }}
        >
          <strong>⏳ Awaiting your review</strong>
          <p className="text-sm" style={{ margin: "4px 0 0" }}>
            Review the patch below and approve or reject it.
          </p>
        </div>
      )}

      {review?.plan && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Plan</h2>
          <pre>{review.plan}</pre>
        </div>
      )}

      {review?.patch && (
        <div className="card">
          <h2>Patch / Diff</h2>
          <pre>{review.patch}</pre>
        </div>
      )}

      {review?.errors && review.errors.length > 0 && (
        <div className="card">
          <h2>Validation Errors</h2>
          <pre>{review.errors.join("\n\n")}</pre>
        </div>
      )}

      {needsReview && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Decision</h2>
          <div className="flex gap-2" style={{ marginTop: 12 }}>
            <button
              className="btn btn-approve"
              onClick={handleApprove}
              disabled={submitting}
            >
              {submitting ? "..." : "👍 Approve"}
            </button>
            <button
              className="btn btn-reject"
              onClick={handleReject}
              disabled={submitting || !feedback.trim()}
            >
              {submitting ? "..." : "❌ Reject"}
            </button>
          </div>
          <div className="mt-2">
            <textarea
              rows={3}
              placeholder="Optional feedback for rejection..."
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
