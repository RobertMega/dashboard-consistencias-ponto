import { NextResponse } from "next/server";
import { createSession, getUserByEmail, passwordMatches, SESSION_COOKIE } from "../../../../lib/auth";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = await request.json() as { email?: string; password?: string };
    const email = body.email?.trim().toLowerCase() ?? "";
    const password = body.password ?? "";
    if (!email || !password || password.length > 256) return NextResponse.json({ error: "Credenciais inválidas." }, { status: 401 });
    const user = await getUserByEmail(email);
    const valid = user ? await passwordMatches(password, user.passwordHash) : false;
    if (!user || !valid) return NextResponse.json({ error: "Credenciais inválidas." }, { status: 401 });
    const token = await createSession(user);
    const response = NextResponse.json({ user: { email: user.email, name: user.name, role: user.role } });
    response.cookies.set(SESSION_COOKIE, token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 60 * 60 * 8 });
    return response;
  } catch {
    return NextResponse.json({ error: "Não foi possível concluir o login." }, { status: 500 });
  }
}
