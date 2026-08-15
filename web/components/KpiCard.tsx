type KpiCardProps = {
  label: string;
  value: string | number;
  tone?: "red" | "orange" | "green" | "navy";
  onClick?: () => void;
  active?: boolean;
};

const icons: Record<string, string> = {
  Colaboradores: "♙",
  "Dias com jornada": "▣",
  "Pontos a justificar": "×",
  "Marcações ímpares": "!",
  "Taxa de conformidade": "✓",
  "Colaboradores críticos": "♙",
  "Saldos finais negativos": "−",
  "Registros OK": "✓",
};

export function KpiCard({ label, value, tone = "navy", onClick, active = false }: KpiCardProps) {
  const handleKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (onClick && (event.key === "Enter" || event.key === " ")) onClick();
  };
  return <article className={`kpi-card kpi-${tone} ${onClick ? "kpi-clickable" : ""} ${active ? "kpi-active" : ""}`} onClick={onClick} onKeyDown={handleKeyDown} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}>
    <span className="kpi-icon" aria-hidden="true">{icons[label] ?? "•"}</span><div className="kpi-content"><span className="kpi-label">{label}</span><strong>{value}</strong></div>
  </article>;
}
