import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Grid2X2, LayoutList, LogOut, ShieldAlert, SlidersHorizontal, SunMoon } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Avatar, ErrorState, Field, Input, Segmented, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { displayName } from "@/lib/types";

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="panel editorial-enter p-6">
      <h2 className="font-display text-lg font-bold">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      <div className="mt-5">{children}</div>
    </div>
  );
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const prefs = usePrefs();
  const { logout } = useAuth();
  const navigate = useNavigate();
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

  const signOutEverywhere = useMutation({
    mutationFn: api.logoutEverywhere,
    onSuccess: () => {
      toast.success("Signed out of every device");
      navigate("/login", { viewTransition: true });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const setTheme = (theme: "light" | "dark") => {
    prefs.update("theme", theme);
    api.updateProfile({ profile: { theme_preference: theme } }).then((data) => queryClient.setQueryData(["me"], data));
  };

  if (user.isPending) {
    return (
      <div className="mx-auto max-w-md space-y-4">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-48 w-full" />
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
      profile: { bio: form.get("bio"), location: form.get("location"), theme_preference: profile.theme_preference },
    });
  };

  return (
    <div className="mx-auto max-w-md space-y-5">
      <Section title="Your profile">
        <div className="mb-5 flex items-center gap-3">
          <Avatar src={profile.avatar} name={displayName(u)} size={56} />
          <p className="text-sm text-muted-foreground">{u.email}</p>
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

          {saved && (
            <p className="animate-fade-in flex items-center gap-1 text-sm font-medium text-success">
              <Check size={14} /> Saved
            </p>
          )}
          <Button type="submit" className="w-full" loading={save.isPending}>
            Save changes
          </Button>
        </form>

        <div className="mt-4 flex flex-col gap-2">
          <Link to="/wallet" className="text-sm font-medium text-primary hover:underline md:hidden">
            View your wallet →
          </Link>
          <Link to="/merchants/apply" className="text-sm font-medium text-primary hover:underline">
            Become a merchant →
          </Link>
        </div>
      </Section>

      <Section title="Display preferences" description="Changes apply instantly and stay saved on this device.">
        <div className="space-y-5">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <SunMoon size={15} /> Appearance
            </div>
            <Segmented options={["light", "dark"] as const} value={prefs.theme} onChange={setTheme} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              {prefs.view === "editorial" ? <LayoutList size={15} /> : <Grid2X2 size={15} />} Feed layout
            </div>
            <Segmented options={["editorial", "grid"] as const} value={prefs.view} onChange={(v) => prefs.update("view", v)} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <SlidersHorizontal size={15} /> Content density
            </div>
            <Segmented options={["comfortable", "compact"] as const} value={prefs.density} onChange={(v) => prefs.update("density", v)} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">Motion</div>
            <Segmented options={["full", "reduced"] as const} value={prefs.motion} onChange={(v) => prefs.update("motion", v)} />
          </div>
        </div>
      </Section>

      <Section title="Security" description="This account doesn't track individual devices, so signing out is all-or-nothing.">
        <Button variant="danger" className="w-full" loading={signOutEverywhere.isPending} onClick={() => signOutEverywhere.mutate()}>
          <ShieldAlert size={15} /> Sign out of all devices
        </Button>
        <button onClick={() => logout().then(() => navigate("/login", { viewTransition: true }))} className="mt-3 flex w-full items-center justify-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <LogOut size={14} /> Just sign out of this device
        </button>
      </Section>
    </div>
  );
}
