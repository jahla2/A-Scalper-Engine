import type { Analysis } from "../types";

export function TimeframeGrid(props: { analysis: Analysis | null }) {
  const item = props.analysis;
  const neutral = !item || item.regime.direction === "NEUTRAL";
  const cards = [
    {
      tf: "1H",
      title: "Strict regime",
      value: item?.regime.direction ?? "NEUTRAL",
      detail: item
        ? "Bias " + item.bias.direction + " " + item.bias.strength +
          " · Structure " + item.regime.structure
        : "Waiting"
    },
    {
      tf: "15M",
      title: "Location",
      value: item?.setup.valid ? "VALID" : neutral ? "SKIPPED" : "INVALID",
      detail: item?.setup.reason ?? "Waiting for 1H"
    },
    {
      tf: "5M",
      title: "Structure",
      value: item?.structure.bos ? "BOS CONFIRMED" : neutral ? "SKIPPED" : "WAITING BOS",
      detail: item?.structure.reason ?? "Not evaluated"
    },
    {
      tf: "1M",
      title: "Execution",
      value: item?.execution.confirmed ? "CONFIRMED" : item?.structure.bos ? "WAITING" : "SKIPPED",
      detail: item?.execution.structure ?? "Not evaluated"
    }
  ];

  return (
    <div className="timeframe-grid">
      {cards.map((card) => (
        <article className="tf-card" key={card.tf}>
          <span className="tf-label">{card.tf}</span>
          <p>{card.title}</p>
          <strong>{card.value}</strong>
          <small>{card.detail}</small>
        </article>
      ))}
    </div>
  );
}
