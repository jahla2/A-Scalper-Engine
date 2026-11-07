import type { Analysis } from "../types";

const labels: Record<string, string> = {
  regime: "1H regime",
  location: "15M location",
  level: "Key level",
  bos: "5M BOS",
  displacement: "Displacement",
  retest: "Retest",
  session: "Session",
  micro: "1M execution",
  rr: "Reward / risk"
};

export function ScorePanel(props: { analysis: Analysis | null }) {
  const total = props.analysis?.score.total ?? 0;
  const threshold = props.analysis?.score.threshold ?? 85;
  const parts = props.analysis?.score.parts ?? {};
  const decision = props.analysis?.decision ?? "NO_TRADE";

  return (
    <section className="panel score-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Confluence</p>
          <h2>A+ setup score</h2>
        </div>
        <span className={"decision decision-" + decision}>
          {decision.replaceAll("_", " ")}
        </span>
      </div>
      <div className="score-main"><strong>{total}</strong><span>/ 100</span></div>
      <div className="score-track">
        <span style={{ width: Math.min(total, 100) + "%" }} />
        <i style={{ left: threshold + "%" }} title={"A+ threshold " + threshold} />
      </div>
      <div className="score-meta">
        <span>Threshold {threshold}</span>
        <span>{props.analysis?.direction ?? "NEUTRAL"}</span>
      </div>
      <div className="score-parts">
        {Object.entries(labels).map(([key, label]) => (
          <div className="score-row" key={key}>
            <span>{label}</span>
            <strong>{parts[key] ?? 0}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
