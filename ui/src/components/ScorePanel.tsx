import type { Analysis, Direction } from "../types";

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

function directionLabel(direction: Direction) {
  if (direction === "LONG") return "LONG BIAS";
  if (direction === "SHORT") return "SHORT BIAS";
  return "MIXED";
}

export function ScorePanel(props: { analysis: Analysis | null }) {
  const total = props.analysis?.score.total ?? 0;
  const threshold = props.analysis?.score.threshold ?? 85;
  const parts = props.analysis?.score.parts ?? {};
  const decision = props.analysis?.decision ?? "NO_TRADE";
  const bias = props.analysis?.bias;
  const biasDirection = bias?.direction ?? "NEUTRAL";
  const longAlignment = bias?.long_alignment ?? 0;
  const shortAlignment = bias?.short_alignment ?? 0;

  return (
    <section className="panel score-panel">
      <div className="bias-section">
        <div className="panel-heading bias-heading">
          <div>
            <p className="eyebrow">Directional alignment</p>
            <h2>Market bias</h2>
          </div>
          <span className={"bias-badge bias-" + biasDirection}>
            {directionLabel(biasDirection)}
          </span>
        </div>

        <div className="bias-summary">
          <strong className={"bias-value bias-" + biasDirection}>
            {bias?.strength ?? 0}
          </strong>
          <span>/ 100 rule alignment</span>
        </div>

        <div className="bias-bars">
          <div className="bias-row">
            <span>Long</span>
            <div className="bias-track">
              <i className="bias-long-fill" style={{ width: longAlignment + "%" }} />
            </div>
            <b>{longAlignment}</b>
          </div>
          <div className="bias-row">
            <span>Short</span>
            <div className="bias-track">
              <i className="bias-short-fill" style={{ width: shortAlignment + "%" }} />
            </div>
            <b>{shortAlignment}</b>
          </div>
        </div>
        <p className="bias-note">Rule alignment only — not a win-rate probability.</p>
      </div>

      <div className="score-divider" />

      <div className="panel-heading score-heading">
        <div>
          <p className="eyebrow">Trade qualification</p>
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
        <span>Strict direction: {props.analysis?.direction ?? "NEUTRAL"}</span>
      </div>

      <div className="score-parts">
        {Object.entries(labels).map(([key, label]) => (
          <div className="score-row" key={key}>
            <span>{label}</span>
            <strong>{parts[key] ?? 0}</strong>
          </div>
        ))}
      </div>

      <div className="strategy-sequence">
        <span>1H regime</span><i>→</i><span>15M location</span><i>→</i>
        <span>5M confirmation</span><i>→</i><span>1M execution</span>
      </div>
    </section>
  );
}
