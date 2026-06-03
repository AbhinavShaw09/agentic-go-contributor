import { NextResponse } from "next/server";
import { listRuns } from "@/lib/runs";

export async function GET() {
  const runs = listRuns();
  return NextResponse.json(runs);
}
