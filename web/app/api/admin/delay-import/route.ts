import { NextResponse } from "next/server";
import { requireAdmin } from "../../../../lib/auth";
import { processAndPersistDelayWorkbook } from "../../../../lib/delayImport";
import { isAllowedDelayUpload, MAX_UPLOAD_BYTES } from "../../../../lib/securityRules";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    await requireAdmin();
    const form = await request.formData();
    const entry = form.get("file");
    if (!(entry instanceof File)) return NextResponse.json({ error: "Selecione um Excel de atrasos." }, { status: 400 });
    if (!isAllowedDelayUpload(entry.name, entry.size, Number(process.env.UPLOAD_MAX_BYTES || MAX_UPLOAD_BYTES))) return NextResponse.json({ error: "O arquivo precisa ser um Excel .xls ou .xlsx válido dentro do limite configurado." }, { status: 400 });
    return NextResponse.json(await processAndPersistDelayWorkbook(entry.name || "atrasos.xlsx", new Uint8Array(await entry.arrayBuffer())));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Falha desconhecida";
    if (!["UNAUTHENTICATED", "FORBIDDEN"].includes(message)) console.error("Delay import failed", { message });
    const status = message === "UNAUTHENTICATED" ? 401 : message === "FORBIDDEN" ? 403 : 422;
    return NextResponse.json({ error: status === 401 ? "Não autenticado." : status === 403 ? "Acesso restrito a administradores." : "Não foi possível importar o Excel de atrasos." }, { status });
  }
}
