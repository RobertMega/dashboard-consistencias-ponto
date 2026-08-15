import { NextResponse } from "next/server";
import { requireAdmin } from "../../../../lib/auth";
import { listReportRuns } from "../../../../lib/reportStore";

export async function GET() {
  try { await requireAdmin(); return NextResponse.json({ runs: await listReportRuns() }); }
  catch (error) { return NextResponse.json({ error: error instanceof Error && error.message === "FORBIDDEN" ? "Acesso restrito a administradores." : "Não autenticado." }, { status: error instanceof Error && error.message === "FORBIDDEN" ? 403 : 401 }); }
}
