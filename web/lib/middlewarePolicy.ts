export function isPublicPath(pathname: string) {
  return pathname === "/login" || pathname.startsWith("/_next/") || pathname === "/favicon.ico" || pathname.startsWith("/api/auth/") || pathname === "/api/parse" || pathname === "/api/export" || pathname.startsWith("/api/automation/") || pathname.startsWith("/logo-motoprama.png") || pathname.startsWith("/.well-known/workflow/");
}
