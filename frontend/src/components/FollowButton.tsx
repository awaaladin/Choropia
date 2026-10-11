import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, useEnsureLogin } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "./Button";

export function FollowButton({ merchantId, className }: { merchantId: number; className?: string }) {
  const { loggedIn } = useAuth();
  const ensureLogin = useEnsureLogin();
  const queryClient = useQueryClient();

  const follows = useQuery({ queryKey: ["follows"], queryFn: api.listMyFollows, enabled: loggedIn });
  const existing = rows(follows.data).find((f) => f.target_type_display === "merchant" && f.object_id === merchantId);

  const toggle = useMutation({
    mutationFn: () => (existing ? api.unfollow(existing.id) : api.follow("merchant", merchantId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follows"] });
      queryClient.invalidateQueries({ queryKey: ["merchant", merchantId] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Button
      variant={existing ? "secondary" : "primary"}
      className={className}
      loading={toggle.isPending}
      onClick={() => ensureLogin() && toggle.mutate()}
    >
      {existing ? <Check size={14} /> : <UserPlus size={14} />}
      {existing ? "Following" : "Follow"}
    </Button>
  );
}
