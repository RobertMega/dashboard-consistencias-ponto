export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function isAdmin(role: string) { return role === "ADMIN"; }
export function isSupportedPdf(filename: string) { return filename.toLowerCase().endsWith(".pdf"); }
export function isAllowedUpload(filename: string, size: number, max = MAX_UPLOAD_BYTES) { return isSupportedPdf(filename) && size > 0 && size <= max; }
