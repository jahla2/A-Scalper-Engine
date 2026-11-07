import type { Analysis } from "../types";

export function TimeframeGrid(props: { analysis: Analysis | null }) {
  const item = props.analysis;
  const cards = [
    {
      tf: "1H",
      title: "Context / regime",
      value: item?.regime.direction ?? "NEUTRAL",
      detail: item
        ? "Bias " + (item.bias?.direction ?? "UNKNOWN") + " " +
          (item.bias?.strength ?? 0) + " · Structure " + item.regime.structure
        : "Waiting for analysis"
    },
    {
      tf: "15M",
      title: "Setup / location",
      value: item?.setup.valid ? "VALID" : "NOT READY",
      detail: item?.setup.reason ?? "Waiting for analysis"
    },
    {
      tf: "5M",
      title: "Confirmation",
      value: item?.structure.bos ? "BOS CONFIRMED" : "NO BOS",
      detail: item
        ? item.structure.reason +
          " · displacement " + (item.structure.displacement ? "yes" : "no") +
          " · retest " + (item.structure.retest ? "yes" : "no")
        : "Waiting for analysis"
    },
    {
      tf: "1M",
      title: "Execution",
      value: item?.execution.confirmed ? "CONFIRMED" : "NOT READY",
      detail: item
        ? "Micro BOS " + (item.execution.micro_bos ? "yes" : "no") +
          " · structure " + item.execution.structure
        : "Waiting for analysis"
    }
  ];

  return (
    <div className="timeframe-grid">
      {cards.map((card) => (
        <article className="tf-card" key={card.tf}>
          <div className="tf-card-top">
            <span className="tf-label">{card.tf}</span>
            <span className="tf-evaluated">EVALUATED</span>
          </div>
          <p>{card.title}</p>
          <strong>{card.value}</strong>
          <small>{card.detail}</small>
        </article>
      ))}
    </div>
  );
}
