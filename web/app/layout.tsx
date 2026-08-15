import "./globals.css";

export const metadata = {
  title: "Relatório Gerencial — Consistências de Ponto",
  description: "Relatório gerencial de consistências de ponto",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
