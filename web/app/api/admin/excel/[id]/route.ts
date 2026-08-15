import { NextResponse } from "next/server";
import { requireAdmin } from "../../../../../lib/auth";
import { prisma } from "../../../../../lib/prisma";

export const runtime = "nodejs";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  try {
    await requireAdmin();
    const run = await prisma.reportRun.findUnique({ where: { id: params.id }, select: { excelData: true, excelFilename: true } });
    if (!run?.excelData) return NextResponse.json({ error: "Excel não encontrado." }, { status: 404 });
    return new NextResponse(run.excelData, { status: 200, headers: { "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "content-disposition": `attachment; filename="${(run.excelFilename || "relatorio.xlsx").replace(/[^a-zA-Z0-9._-]/g, "_")}"`, "cache-control": "private, no-store" } });
  } catch (error) { return NextResponse.json({ error: error instanceof Error && error.message === "FORBIDDEN" ? "Acesso restrito a administradores." : "Não autenticado." }, { status: error instanceof Error && error.message === "FORBIDDEN" ? 403 : 401 }); }
}
