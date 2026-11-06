import { Download, Globe } from "lucide-react";
import { PublicShell } from "@/components/PublicShell";

/** Both QR codes on one printable page: one downloads the Android app, the other opens the website. */
export function GetAppPage() {
  return (
    <PublicShell>
      <section className="mx-auto max-w-3xl px-5 py-14 text-center">
        <p className="eyebrow">GET CHOROPIA</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">Scan, then start</h1>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">Point your phone camera at a code. No typing needed.</p>

        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          <div className="panel flex flex-col items-center p-6">
            <img src="/qr/download-app.png" alt="QR code that downloads the Choropia Android app" className="size-52 rounded-lg bg-white p-2" />
            <h2 className="mt-4 flex items-center gap-2 text-lg font-semibold">
              <Download size={18} /> Download the app
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">Android. Scan and the download starts.</p>
            <a href="/downloads/choropia.apk" download className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
              Or tap to download
            </a>
          </div>
          <div className="panel flex flex-col items-center p-6">
            <img src="/qr/visit-website.png" alt="QR code that opens the Choropia website" className="size-52 rounded-lg bg-white p-2" />
            <h2 className="mt-4 flex items-center gap-2 text-lg font-semibold">
              <Globe size={18} /> Visit the website
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">Scan to open choropia.vercel.app.</p>
            <a href="/" className="mt-4 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-accent">
              Or open it here
            </a>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}
