import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

type ProcessPayload = {
  metadata: { period_start?: string | null; period_end?: string | null; records?: number; pages?: number; source_pdf?: string | null };
  summary: Record<string, unknown>;
  records: Array<Record<string, unknown>>;
};

function runProcess(pdfPath: string, jsonPath: string, excelPath: string) {
  const repoRoot = path.resolve(process.cwd(), "..");
  const python = process.env.PYTHON_BIN || "python";
  return new Promise<void>((resolve, reject) => {
    const child = spawn(python, ["-m", "automation.process_report", pdfPath, "--json", jsonPath, "--excel", excelPath], { cwd: repoRoot, windowsHide: true });
    let stderr = "";
    child.stderr.on("data", (chunk) => { stderr += String(chunk); });
    const timer = setTimeout(() => { child.kill(); reject(new Error("O processamento excedeu o tempo limite.")); }, 5 * 60 * 1000);
    child.on("error", (error) => { clearTimeout(timer); reject(error); });
    child.on("close", (code) => { clearTimeout(timer); if (code === 0) resolve(); else reject(new Error(stderr.slice(-2000) || `Processamento encerrado com código ${code}.`)); });
  });
}

async function runRemoteProcess(filename: string, bytes: Uint8Array) {
  const configuredUrl = process.env.PARSER_FUNCTION_URL;
  const vercelUrl = process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null;
  const baseUrl = configuredUrl || vercelUrl;
  const token = process.env.PARSER_SERVICE_TOKEN;
  if (!baseUrl || !token) throw new Error("Processador Python de produção não configurado.");
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/parse`, { method: "POST", headers: { "content-type": "application/pdf", "content-length": String(bytes.byteLength), "x-file-name": filename, "x-parser-token": token }, body: Buffer.from(bytes) });
  const result = await response.json() as { payload?: ProcessPayload; excel?: string; error?: string };
  if (!response.ok || !result.payload || !result.excel) throw new Error(result.error || "Falha no processamento Python.");
  return { payload: result.payload, excel: Buffer.from(result.excel, "base64") };
}

export async function processUploadedPdf(filename: string, bytes: Uint8Array) {
  const stagingRoot = path.resolve(process.cwd(), "..", "data", ".staging");
  await mkdir(stagingRoot, { recursive: true });
  const directory = await mkdtemp(path.join(stagingRoot, "dashboard-ponto-"));
  const safeName = path.basename(filename).replace(/[^a-zA-Z0-9._-]/g, "_");
  const pdfPath = path.join(directory, safeName || "report.pdf");
  const jsonPath = path.join(directory, "result.json");
  const excelPath = path.join(directory, "result.xlsx");
  try {
    if (process.env.VERCEL === "1" || process.env.PARSER_FUNCTION_URL) return await runRemoteProcess(filename, bytes);
    await writeFile(pdfPath, bytes, { flag: "wx" });
    await runProcess(pdfPath, jsonPath, excelPath);
    const payload = JSON.parse(await readFile(jsonPath, "utf8")) as ProcessPayload;
    const excel = await readFile(excelPath);
    if (!payload.metadata.period_start || !payload.metadata.period_end || !Array.isArray(payload.records) || payload.records.length === 0) throw new Error("O processamento não produziu uma base válida.");
    return { payload, excel };
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
