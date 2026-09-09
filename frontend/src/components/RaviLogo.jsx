export default function RaviLogo({ size = 34, withName = true }) {
  return (
    <div className="flex items-center gap-2.5" data-testid="ravi-logo">
      <div
        className="brand-gradient rounded-lg flex items-center justify-center ravi-glow shrink-0"
        style={{ width: size, height: size }}
      >
        <span
          className="font-display font-extrabold text-white"
          style={{ fontSize: size * 0.58, lineHeight: 1 }}
        >
          R
        </span>
      </div>
      {withName && (
        <span className="font-display font-bold text-lg tracking-tight text-zinc-100">RAVI</span>
      )}
    </div>
  );
}
