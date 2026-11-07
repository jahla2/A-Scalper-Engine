import type { Analysis } from "../types";

function price(value: number | undefined) {
  if (value === undefined) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6
  });
}

export function TradePlanCard(props: { analysis: Analysis | null }) {
  const analysis = props.analysis;
  const plan = analysis?.trade;

  if (!plan) {
    return (
      <section className="panel trade-plan-panel trade-plan-empty">
        <div className="trade-plan-heading">
          <div>
            <p className="eyebrow">Structured trade plan</p>
            <h2>No valid entry plan yet</h2>
          </div>
          <span className="plan-status plan-waiting">WAITING</span>
        </div>
        <p>
          The engine will only publish Entry, SL and TP levels after a confirmed 5M BOS
          provides a structural invalidation point and at least {analysis?.score.threshold ?? 85}
          setup-quality context.
        </p>
        <small>
          Current blocker: {analysis?.reasons?.[0] ?? "Waiting for the next completed analysis."}
        </small>
      </section>
    );
  }

  const direction = analysis?.direction ?? "NEUTRAL";
  const ready = plan.status === "READY" && analysis?.decision === "TRADE_CANDIDATE";

  return (
    <section className="panel trade-plan-panel">
      <div className="trade-plan-heading">
        <div>
          <p className="eyebrow">Structured trade plan</p>
          <h2>
            {direction} levels
            <span className={"trade-direction trade-direction-" + direction}>{direction}</span>
          </h2>
        </div>
        <span className={"plan-status " + (ready ? "plan-ready" : "plan-provisional")}>
          {ready ? "READY" : plan.status}
        </span>
      </div>

      <div className="trade-level-grid">
        <Level label="Entry" value={plan.entry} kind="entry" />
        <Level label="Stop loss" value={plan.stop_loss} kind="sl" />
        <Level label={"TP1 · " + plan.rr1.toFixed(2) + "R"} value={plan.tp1} kind="tp" />
        <Level label={"TP2 · " + plan.rr2.toFixed(2) + "R"} value={plan.tp2} kind="tp" />
        <Level label={"TP3 · " + plan.rr3.toFixed(2) + "R"} value={plan.tp3} kind="tp" />
      </div>

      <div className="trade-plan-meta">
        <span>Risk budget <strong>{plan.risk_budget.toFixed(2)}</strong></span>
        <span>Final RR <strong>{plan.rr3.toFixed(2)}R</strong></span>
        <span>
          15M obstacle <strong>{plan.obstacle === null ? "None" : price(plan.obstacle)}</strong>
        </span>
      </div>

      <div className="trade-rationale">
        <Reason title="Entry" text={plan.entry_reason} />
        <Reason title="SL" text={plan.stop_reason} />
        <Reason title="TP1" text={plan.tp1_reason} />
        <Reason title="TP2" text={plan.tp2_reason} />
        <Reason title="TP3" text={plan.tp3_reason} />
      </div>

      {!ready && (
        <div className="plan-warning">
          Levels are provisional. Do not treat them as an entry signal until the dashboard
          shows TRADE CANDIDATE and the required 5M/1M confirmations are complete.
        </div>
      )}
    </section>
  );
}

function Level(props: { label: string; value: number; kind: "entry" | "sl" | "tp" }) {
  return (
    <div className={"trade-level trade-level-" + props.kind}>
      <span>{props.label}</span>
      <strong>{price(props.value)}</strong>
    </div>
  );
}

function Reason(props: { title: string; text: string }) {
  return (
    <div>
      <strong>{props.title}</strong>
      <span>{props.text}</span>
    </div>
  );
}
