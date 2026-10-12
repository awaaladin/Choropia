import { Smartphone } from "lucide-react";
import { cn } from "@/lib/utils";

/** The signed release APK, dropped at this exact path by the Android build (see
 * frontend/public/downloads/) and served statically — not a React Router route. */
const APK_PATH = "/downloads/choropia.apk";

export function DownloadAppLink({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <a href={APK_PATH} download className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-primary", className)}>
      <Smartphone size={compact ? 14 : 15} />
      {compact ? "Get the app" : "Get the Choropia Android app"}
    </a>
  );
}
