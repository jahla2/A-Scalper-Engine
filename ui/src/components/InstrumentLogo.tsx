import { Gem } from "lucide-react";

export function InstrumentLogo(props: { symbol: string; size?: number }) {
  const size = props.size ?? 32;
  const asset = baseAsset(props.symbol);

  if (asset === "BTC") {
    return (
      <span className="instrument-logo instrument-logo-btc" style={{ width: size, height: size }}>
        ₿
      </span>
    );
  }

  if (asset === "ETH") {
    return (
      <span className="instrument-logo instrument-logo-eth" style={{ width: size, height: size }}>
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d="M16 3 8.7 16 16 20.2 23.3 16 16 3Z" />
          <path d="m8.7 17.8 7.3 11.1 7.3-11.1L16 22l-7.3-4.2Z" opacity=".72" />
        </svg>
      </span>
    );
  }

  if (asset === "SOL") {
    return (
      <span className="instrument-logo instrument-logo-sol" style={{ width: size, height: size }}>
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d="M8 7h17l-4 4H4l4-4Zm3 7h17l-4 4H7l4-4Zm-3 7h17l-4 4H4l4-4Z" />
        </svg>
      </span>
    );
  }

  if (asset === "XAU" || asset === "GOLD") {
    return (
      <span className="instrument-logo instrument-logo-gold" style={{ width: size, height: size }}>
        <Gem size={Math.max(16, size * 0.5)} />
      </span>
    );
  }

  if (asset === "XRP") {
    return (
      <span className="instrument-logo instrument-logo-xrp" style={{ width: size, height: size }}>
        X
      </span>
    );
  }

  return (
    <span className="instrument-logo instrument-logo-generic" style={{ width: size, height: size }}>
      {asset.slice(0, 3)}
    </span>
  );
}

function baseAsset(symbol: string) {
  return symbol.split(/[/.:-]/)[0]?.toUpperCase() || "?";
}
