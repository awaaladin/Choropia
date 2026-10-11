import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Avatar, ErrorState, Field, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { displayName } from "@/lib/types";

export function ProfilePage() {
  const queryClient = useQueryClient();
  const prefs = usePrefs();
  const user = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 3000);
    return () => clearTimeout(t);
  }, [saved]);

  const save = useMutation({
    mutationFn: api.updateProfile,
    onSuccess: (data) => {
      queryClient.setQueryData(["me"], data);
      setSaved(true);
      prefs.update("theme", data.profile!.theme_preference);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (user.isPending) {
    return (
      <div className="mx-auto max-w-md">
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (user.isError) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorState message={(user.error as Error).message} onRetry={() => user.refetch()} />
      </div>
    );
  }

  const u = user.data!;
  const profile = u.profile!;

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    save.mutate({
      first_name: form.get("first_name"),
      last_name: form.get("last_name"),
      phone_number: form.get("phone_number") || null,
      profile: { bio: form.get("bio"), location: form.get("location"), theme_preference: form.get("theme_preference") },
    });
  };

  return (
    <div className="mx-auto max-w-md">
      <div className="panel editorial-enter p-6">
        <div className="mb-5 flex items-center gap-3">
          <Avatar src={profile.avatar} name={displayName(u)} size={56} />
          <div>
            <h1 className="font-display text-xl font-bold">Your profile</h1>
            <p className="text-sm text-muted-foreground">{u.email}</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="First name">
              <Input name="first_name" defaultValue={u.first_name} />
            </Field>
            <Field label="Last name">
              <Input name="last_name" defaultValue={u.last_name} />
            </Field>
          </div>
          <Field label="Phone number">
            <Input name="phone_number" defaultValue={u.phone_number ?? ""} />
          </Field>
          <Field label="Bio">
            <Textarea name="bio" rows={2} defaultValue={profile.bio} />
          </Field>
          <Field label="Location">
            <Input name="location" defaultValue={profile.location} />
          </Field>
          <Field label="Theme">
            <Select name="theme_preference" defaultValue={profile.theme_preference}>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </Select>
          </Field>

          {saved && (
            <p className="animate-fade-in flex items-center gap-1 text-sm font-medium text-success">
              <Check size={14} /> Saved
            </p>
          )}
          <Button type="submit" className="w-full" loading={save.isPending}>
            Save changes
          </Button>
        </form>

        <Link to="/merchants/apply" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
          Become a merchant →
        </Link>
      </div>
    </div>
  );
}
