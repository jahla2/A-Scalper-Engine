import type { Analysis } from "../types";

export function AnalysisLog(props: { items: Analysis[] }) {
  return (
    <section className="panel log-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">Engine activity</p><h2>Analysis timeline</h2></div>
      </div>
      <div className="log-list">
        {props.items.length === 0 && <div className="empty">No analysis events yet.</div>}
        {props.items.slice(0, 12).map((item, index) => (
          <div className="log-row" key={item.timestamp + "-" + index}>
            <time>{new Date(item.timestamp * 1000).toLocaleTimeString()}</time>
            <span className={"direction direction-" + item.direction}>{item.direction}</span>
            <div className="log-copy">
              <strong>{item.decision.replaceAll("_", " ")}</strong>
              <small>{item.reasons?.[0] ?? "Analysis completed"}</small>
            </div>
            <b>{item.score.total}</b>
          </div>
        ))}
      </div>
    </section>
  );
}
