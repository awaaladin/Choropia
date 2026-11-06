import { Download } from "lucide-react";
import { Link } from "./AppLink";

/** A small "get the Android app" prompt for the sign-up and login pages. */
export function AppDownloadCard() {
  return (
    <div className="mt-6 flex items-center gap-3 rounded-lg border border-border bg-accent/40 p-3">
      <img src="/qr/download-app.png" alt="Scan to download the Choropia app" width={64} height={64} className="hidden size-16 shrink-0 rounded-md bg-white p-1 sm:block" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Prefer the app?</p>
        <p className="text-xs text-muted-foreground">Get Choropia for Android. Faster, with order alerts.</p>
      </div>
      <a
        href="/downloads/choropia.apk"
        download
        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
      >
        <Download size={15} /> Download
      </a>
      <Link to="/get-app" className="sr-only">
        More ways to get the app
      </Link>
    </div>
  );
}
