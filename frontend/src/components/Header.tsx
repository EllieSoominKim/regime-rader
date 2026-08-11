import Image from "next/image";
import Link from "next/link";

/**
 * Top-left brand lockup: small radar icon mark + "regime-rader" wordmark
 * text + a HUD-style "REGIME RADAR" English eyebrow underneath, per the
 * mockup. wordmark_horizontal.png (also in public/) is not used here --
 * the mockup's header renders the name as live text beside the icon, not
 * the flattened wordmark image; that asset is available for places that
 * need a single flattened lockup (e.g. share cards) later.
 */
export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-md items-center gap-2.5 px-4 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <Image
            src="/icon_transparent_1024.png"
            alt="regime-rader"
            width={36}
            height={36}
            className="h-9 w-9"
            priority
          />
          <span className="flex flex-col leading-none">
            <span className="font-kr text-lg font-black tracking-tight text-text">
              regime-rader
            </span>
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-muted-2">
              Regime Radar
            </span>
          </span>
        </Link>
      </div>
    </header>
  );
}
