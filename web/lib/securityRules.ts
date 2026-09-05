import { timingSafeEqual } from "node:crypto";

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function isAdmin(role: string) { return role === "ADMIN"; }
export function isSupportedPdf(filename: string) { return filename.toLowerCase().endsWith(".pdf"); }
export function isAllowedUpload(filename: string, size: number, max = MAX_UPLOAD_BYTES) { return isSupportedPdf(filename) && size > 0 && size <= max; }
export function isSupportedSpreadsheet(filename: string) { return [".xls", ".xlsx"].some((extension) => filename.toLowerCase().endsWith(extension)); }
export function isAllowedDelayUpload(filename: string, size: number, max = MAX_UPLOAD_BYTES) { return isSupportedSpreadsheet(filename) && size > 0 && size <= max; }
export function isAllowedAbsenceUpload(filename: string, size: number, max = MAX_UPLOAD_BYTES) { return isSupportedSpreadsheet(filename) && size > 0 && size <= max; }

export function tokensMatch(expected: string | undefined, supplied: string | undefined) {
  if (!expected || !supplied) return false;
  const expectedBytes = Buffer.from(expected);
  const suppliedBytes = Buffer.from(supplied);
  return expectedBytes.length === suppliedBytes.length && timingSafeEqual(expectedBytes, suppliedBytes);
}
