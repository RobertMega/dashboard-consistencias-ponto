"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null);
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password }) });
      const body = await response.json() as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "Credenciais inválidas.");
      router.replace("/"); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível entrar."); }
    finally { setLoading(false); }
  }
  return <main className="login-page"><section className="login-card"><div className="login-brand">HONDA MOTOPRAMA</div><h1>Acesso ao relatório gerencial</h1><p>Entre com seu usuário corporativo autorizado.</p><form onSubmit={submit}><label htmlFor="email">E-mail</label><input id="email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /><label htmlFor="password">Senha</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />{error && <div className="login-error">{error}</div>}<button type="submit" disabled={loading}>{loading ? "Entrando…" : "Entrar"}</button></form></section></main>;
}
