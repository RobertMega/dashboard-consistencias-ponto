import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isPublic = pathname === "/login" || pathname.startsWith("/_next/") || pathname === "/favicon.ico" || pathname.startsWith("/api/auth/") || pathname === "/api/parse" || pathname === "/api/export" || pathname.startsWith("/logo-motoprama.png");
  if (isPublic) return NextResponse.next();
  if (!request.cookies.has("dashboard_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
