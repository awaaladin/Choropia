import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { errorMessage, useEnsureLogin } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "./Button";

interface FollowButtonProps {
  targetId: number;
  targetType?: "merchant" | "user";
  className?: string;
}

export function FollowButton({ targetId, targetType = "merchant", className }: FollowButtonProps) {
  const { loggedIn } = useAuth();
  const ensureLogin = useEnsureLogin();
  const queryClient = useQueryClient();

  const follows = useQuery({ queryKey: ["follows"], queryFn: api.listMyFollows, enabled: loggedIn });
  const existing = rows(follows.data).find((f) => f.target_type_display === targetType && f.object_id === targetId);

  const [justFollowed, setJustFollowed] = useState(false);
  useEffect(() => {
    if (!justFollowed) return;
    const t = setTimeout(() => setJustFollowed(false), 2500);
    return () => clearTimeout(t);
  }, [justFollowed]);

  const toggle = useMutation({
    mutationFn: () => (existing ? api.unfollow(existing.id) : api.follow(targetType, targetId)),
    onSuccess: () => {
      setJustFollowed(!existing);
      queryClient.invalidateQueries({ queryKey: ["follows"] });
      queryClient.invalidateQueries({ queryKey: [targetType, targetId] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Button
      variant={existing && !justFollowed ? "secondary" : "primary"}
      className={className}
      loading={toggle.isPending}
      onClick={() => ensureLogin() && toggle.mutate()}
    >
      {existing ? justFollowed ? <Check size={14} /> : null : <UserPlus size={14} />}
      {existing ? "Following" : "Follow"}
    </Button>
  );
}
