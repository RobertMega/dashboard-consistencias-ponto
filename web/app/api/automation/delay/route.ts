import { NextResponse } from "next/server";
import { processAndPersistDelayWorkbook } from "../../../../lib/delayImport";
import { automationRequestError } from "../../../../lib/automationRequest";
import { isAllowedDelayUpload, MAX_UPLOAD_BYTES } from "../../../../lib/securityRules";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const expectedToken = process.env.AUTOMATION_TOKEN;
  if (!expectedToken) return NextResponse.json({ error: "Automação não configurada neste ambiente." }, { status: 503 });

  const reportDate = request.headers.get("x-report-date")?.trim() || "";
  const requestError = automationRequestError(expectedToken, request.headers.get("x-automation-token") || undefined, reportDate);
  if (requestError === "UNAUTHORIZED") return NextResponse.json({ error: "Não autorizado." }, { status: 401 });
  if (requestError === "INVALID_DATE") return NextResponse.json({ error: "Data do relatório inválida." }, { status: 400 });

  try {
    const form = await request.formData();
    const entry = form.get("file");
    if (!(entry instanceof File)) return NextResponse.json({ error: "Selecione um Excel de atrasos." }, { status: 400 });
    if (!isAllowedDelayUpload(entry.name, entry.size, Number(process.env.UPLOAD_MAX_BYTES || MAX_UPLOAD_BYTES))) {
      return NextResponse.json({ error: "O arquivo precisa ser um Excel .xls ou .xlsx válido dentro do limite configurado." }, { status: 400 });
    }
    return NextResponse.json(await processAndPersistDelayWorkbook(entry.name || "atrasos.xlsx", new Uint8Array(await entry.arrayBuffer()), reportDate));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Falha desconhecida";
    console.error("Automated delay import failed", { message });
    if (message === "REPORT_DATE_MISMATCH") return NextResponse.json({ error: "O relatório de atrasos não corresponde à data D-1 solicitada." }, { status: 422 });
    return NextResponse.json({ error: "Não foi possível importar o relatório automático de atrasos." }, { status: 422 });
  }
}
