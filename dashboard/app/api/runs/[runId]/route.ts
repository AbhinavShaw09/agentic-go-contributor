import { NextRequest, NextResponse } from "next/server";
import { getRun, writeDecision } from "@/lib/runs";

export async function GET(
  _req: NextRequest,
  { params }: { params: { runId: string } }
) {
  const run = getRun(params.runId);
  if (!run) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json(run);
}

export async function POST(
  req: NextRequest,
  { params }: { params: { runId: string } }
) {
  const body = await req.json();
  const { approved, feedback } = body;

  if (typeof approved !== "boolean") {
    return NextResponse.json(
      { error: "approved must be a boolean" },
      { status: 400 }
    );
  }

  const ok = writeDecision(params.runId, approved, feedback || "");
  if (!ok) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }

  return NextResponse.json({ ok: true });
}
