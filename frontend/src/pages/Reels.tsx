import { useQuery } from "@tanstack/react-query";
import { Clapperboard, Plus } from "lucide-react";
import { ReelCard } from "@/components/ReelCard";
import { LinkButton } from "@/components/Button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";

export function ReelsPage() {
  const reels = useQuery({ queryKey: ["reels"], queryFn: async () => rows(await api.listReels()) });

  return (
    <>
      {/* Edge-to-edge like most vertical-video feeds — escapes AppShell's padded/max-width
          <main> deliberately, positioned against the sticky header (4rem) and, on mobile, the
          fixed bottom tab bar (also 4rem) so the feed fills exactly what's left between them. */}
      <div className="fixed inset-x-0 bottom-16 top-16 z-0 md:bottom-0">
        {reels.isPending && (
          <div className="p-4">
            <Skeleton className="h-full w-full" />
          </div>
        )}
        {reels.isError && (
          <div className="p-4">
            <ErrorState message={(reels.error as Error).message} onRetry={() => reels.refetch()} />
          </div>
        )}
        {reels.isSuccess && reels.data.length === 0 && (
          <div className="grid h-full place-items-center p-4">
            <EmptyState icon={<Clapperboard size={20} />} title="No reels yet" hint="Be the first to post a short video of what you're selling." />
          </div>
        )}
        {reels.data && reels.data.length > 0 && (
          <div className="mx-auto flex h-full max-w-md snap-y snap-mandatory flex-col overflow-y-auto md:py-3">
            {reels.data.map((reel) => (
              <ReelCard key={reel.id} reel={reel} />
            ))}
          </div>
        )}
      </div>

      <LinkButton to="/reels/new" variant="secondary" className="fixed right-4 top-20 z-10 h-9 px-3 text-xs shadow-lg">
        <Plus size={14} /> Create
      </LinkButton>
    </>
  );
}
