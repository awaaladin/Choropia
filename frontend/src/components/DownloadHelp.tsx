import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const STEPS = [
  ["The download didn't start.", "Open this page in Chrome (in-app browsers inside Instagram, Facebook or WhatsApp often block downloads) and make sure you have about 40MB free."],
  ['Chrome says "this type of file can harm your device."', "Tap Download anyway. That warning appears for every app installed outside the Play Store."],
  ["Install blocked.", 'Go to Settings → Apps → Special access → Install unknown apps, choose Chrome, turn on Allow from this source. Then open Choropia.apk from your Downloads folder and tap Install.'],
  ['"App not installed."', "Uninstall any older Choropia build first, then install again. Choropia needs Android 8.0 or newer."],
  ["Play Protect warning.", "Tap More details, then Install anyway. The app is not on the Play Store yet."],
  ["Still stuck?", "The web app has the same account and orders, so you can keep using it while you sort out the install."],
] as const;

/** Collapsible install troubleshooting for the Android APK — suggested by the Android session,
 * which isn't on the Play Store yet so this warning/unknown-sources friction is expected. */
export function DownloadHelp({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cn("text-sm", className)}>
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex items-center gap-1.5 font-medium text-muted-foreground transition-colors hover:text-primary">
        Having trouble installing?
        <ChevronDown size={14} className={cn("transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="animate-fade-in mt-3 list-decimal space-y-3 pl-5 text-sm leading-6 text-muted-foreground">
          {STEPS.map(([title, copy]) => (
            <li key={title}>
              <span className="font-medium text-foreground">{title}</span> {copy}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
