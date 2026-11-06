import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Camera, FileUp, MapPin, Truck } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { AreaSelect } from "@/components/AreaSelect";
import { ErrorState, Field, Input, Modal, Pill, Select, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import type { Area, DriverMe, OrderDelivery } from "@/lib/types";
import { naira } from "@/lib/utils";

const VEHICLES = [
  ["bike", "Motorbike"],
  ["tricycle", "Tricycle (keke)"],
  ["car", "Car"],
  ["van", "Van / bus"],
] as const;

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="panel editorial-enter p-6">
      {title && <h2 className="font-display text-lg font-bold">{title}</h2>}
      <div className={title ? "mt-4" : ""}>{children}</div>
    </div>
  );
}

/** Deliver with Choropia: apply, upload documents, publish prices, take jobs. One page for the whole driver journey. */
export function DriverPage() {
  const me = useQuery({ queryKey: ["driver-me"], queryFn: api.dispatch.driverMe });
  if (me.isPending) return <Skeleton className="mx-auto h-72 max-w-xl" />;
  if (me.isError) return <ErrorState message="We couldn't load your driver profile." onRetry={() => me.refetch()} />;
  const profile = me.data;
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h1 className="flex items-center gap-2 font-display text-2xl font-bold">
          <Truck size={22} /> Deliver with Choropia
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Earn by delivering items sold on Choropia. You set a fixed price for each trip, and we verify every driver first so buyers and sellers can trust you.
        </p>
      </div>
      {!profile ? <ApplyForm /> : profile.status === "approved" ? <Hub profile={profile} /> : <Review profile={profile} />}
    </div>
  );
}

// --- applying ----------------------------------------------------------------------------------------------------

function ApplyForm() {
  const queryClient = useQueryClient();
  const [accepted, setAccepted] = useState(false);
  const apply = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.dispatch.apply(body),
    onSuccess: () => {
      toast.success("Application sent. Now upload your documents.");
      queryClient.invalidateQueries({ queryKey: ["driver-me"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    apply.mutate({
      full_name: f.get("full_name"),
      phone: f.get("phone"),
      whatsapp: f.get("whatsapp"),
      vehicle_type: f.get("vehicle_type"),
      plate_number: f.get("plate_number"),
      guarantor_name: f.get("guarantor_name"),
      guarantor_phone: f.get("guarantor_phone"),
      accept_terms: accepted,
    });
  };
  return (
    <Card title="Apply to be a driver">
      <p className="mb-4 text-sm text-muted-foreground">Individual drivers only for now. You will need your phone, WhatsApp, a guarantor, and clear photos of any two of these: driver's licence or ID, passport photograph, guarantor form, vehicle papers.</p>
      <div className="mb-5 rounded-xl border border-border bg-accent/50 p-4 text-sm">
        <p className="font-semibold">Your documents are private and encrypted</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
          <li>Every document is scrambled (encrypted) the moment you upload it, before it is saved.</li>
          <li>Only Choropia's small verification team can open them, and every time one is opened it is written in a log.</li>
          <li>We never show them to sellers, buyers or other drivers, and we never sell or share them with anyone. The only exception is if the law forces us to.</li>
          <li>If we can't approve you, your documents are deleted automatically after 30 days.</li>
        </ul>
        <p className="mt-2 text-muted-foreground">
          Read the full <a className="font-medium text-primary underline" href="/legal/privacy/" target="_blank" rel="noreferrer">Privacy Policy</a>.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Full name (as on your ID)">
          <Input name="full_name" required />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Phone number">
            <Input name="phone" inputMode="tel" required placeholder="08012345678" />
          </Field>
          <Field label="WhatsApp number">
            <Input name="whatsapp" inputMode="tel" required placeholder="08012345678" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Your vehicle">
            <Select name="vehicle_type" defaultValue="bike">
              {VEHICLES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Plate number (if any)">
            <Input name="plate_number" />
          </Field>
        </div>
        <p className="text-sm font-medium">Your guarantor</p>
        <p className="-mt-3 text-sm text-muted-foreground">Someone who knows you and can vouch for you. We may call them to confirm.</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Guarantor's full name">
            <Input name="guarantor_name" required />
          </Field>
          <Field label="Guarantor's phone">
            <Input name="guarantor_phone" inputMode="tel" required />
          </Field>
        </div>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
          <span>
            I agree to the{" "}
            <a className="font-medium text-primary underline" href="/legal/driver_terms/" target="_blank" rel="noreferrer">
              Driver Terms
            </a>{" "}
            and the{" "}
            <a className="font-medium text-primary underline" href="/legal/privacy/" target="_blank" rel="noreferrer">
              Privacy Policy
            </a>
            , and I consent to my documents being checked.
          </span>
        </label>
        <Button type="submit" loading={apply.isPending} disabled={!accepted}>
          Apply
        </Button>
      </form>
    </Card>
  );
}

// --- waiting for review / rejected / suspended ------------------------------------------------------------------------

function Review({ profile }: { profile: DriverMe }) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<string | null>(null);
  const upload = useMutation({
    mutationFn: ({ kind, file }: { kind: string; file: File }) => api.dispatch.uploadDocument(kind, file),
    onSuccess: (updated) => {
      toast.success(updated.documents_complete ? "That's enough. Your application is submitted." : "Document uploaded securely.");
      queryClient.setQueryData(["driver-me"], updated);
      queryClient.invalidateQueries({ queryKey: ["driver-me"] });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const message =
    profile.status === "rejected"
      ? profile.review_note || "We couldn't verify your application. Fix the details and apply again."
      : profile.status === "suspended"
        ? profile.review_note || "Your driver account is suspended. Contact support."
        : profile.documents_complete
          ? "We have everything. Our team is checking your documents. You'll get an email when you're approved."
          : "Upload any two documents below so we can verify you.";
  const uploaded = profile.documents.filter((d) => d.uploaded).length;
  const submitted = profile.status === "pending" && profile.documents_complete;
  return (
    <>
      {submitted ? (
        <Card>
          <div className="text-center">
            <div className="mx-auto grid size-14 place-items-center rounded-full bg-success/15 text-success">
              <CheckCircle2 size={30} />
            </div>
            <h2 className="mt-3 font-display text-xl font-bold">Application submitted</h2>
            <p className="mt-1 text-sm text-muted-foreground">Thank you, {profile.full_name.split(" ")[0]}. You don't need to do anything else right now.</p>
          </div>
          <ol className="mt-5 space-y-3 text-sm">
            <li className="flex gap-3"><CheckCircle2 size={18} className="mt-0.5 shrink-0 text-success" /> <span><strong>Your details</strong> are saved.</span></li>
            <li className="flex gap-3"><CheckCircle2 size={18} className="mt-0.5 shrink-0 text-success" /> <span><strong>Your documents</strong> are uploaded and locked away safely.</span></li>
            <li className="flex gap-3"><span className="mt-0.5 grid size-[18px] shrink-0 place-items-center rounded-full border-2 border-primary text-[10px] font-bold text-primary">3</span> <span><strong>We check your documents</strong> and call your guarantor. You'll get an email when you're approved.</span></li>
            <li className="flex gap-3"><span className="mt-0.5 grid size-[18px] shrink-0 place-items-center rounded-full border-2 border-border text-[10px] font-bold text-muted-foreground">4</span> <span><strong>Then you come back here</strong> to add your trips and prices, and start getting delivery jobs.</span></li>
          </ol>
          <div className="mt-5 flex gap-3">
            <Link to="/feed" className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">Back to Choropia</Link>
            <a href="/legal/driver_terms/" target="_blank" rel="noreferrer" className="self-center text-sm text-primary underline">Driver Terms</a>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="flex items-center gap-2">
            <Pill active>{profile.status_label}</Pill>
            {profile.status === "pending" && <span className="text-sm text-muted-foreground">{uploaded} documents uploaded (any 2 are enough)</span>}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{message}</p>
        </Card>
      )}
      {profile.status !== "suspended" && !submitted && (
        <Card title="Your documents">
          <p className="mb-3 text-sm text-muted-foreground">They are encrypted on our servers. Only our verification team can open them, every view is logged, and we never share them with anyone.</p>
          <input
            ref={input}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file && kind) upload.mutate({ kind, file });
              e.target.value = "";
            }}
          />
          <ul className="divide-y divide-border">
            {profile.documents.map((doc) => (
              <li key={doc.kind} className="flex items-center justify-between gap-3 py-3">
                <span className="flex items-center gap-2 text-sm">
                  {doc.uploaded ? <CheckCircle2 size={16} className="text-success" /> : <FileUp size={16} className="text-muted-foreground" />}
                  {doc.label}
                </span>
                <Button
                  variant="secondary"
                  loading={upload.isPending && kind === doc.kind}
                  onClick={() => {
                    setKind(doc.kind);
                    input.current?.click();
                  }}
                >
                  {doc.uploaded ? "Replace" : "Upload"}
                </Button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">A JPG or PNG photo, up to 3 MB. A PDF is fine for everything except the passport photograph.</p>
        </Card>
      )}
    </>
  );
}

// --- approved: jobs, prices, account -------------------------------------------------------------------------------------

function Hub({ profile }: { profile: DriverMe }) {
  const [tab, setTab] = useState<"jobs" | "prices" | "account">("jobs");
  return (
    <>
      <div className="flex gap-2">
        {(["jobs", "prices", "account"] as const).map((t) => (
          <Pill key={t} active={tab === t} onClick={() => setTab(t)}>
            {t === "jobs" ? "Jobs" : t === "prices" ? "My prices" : "Account"}
          </Pill>
        ))}
      </div>
      {tab === "jobs" && <Jobs />}
      {tab === "prices" && <Prices />}
      {tab === "account" && <Account profile={profile} />}
    </>
  );
}

function Jobs() {
  const queryClient = useQueryClient();
  const jobs = useQuery({ queryKey: ["driver-jobs"], queryFn: api.dispatch.jobs, refetchInterval: 15_000 });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["driver-jobs"] });
  const accept = useMutation({ mutationFn: (id: number) => api.dispatch.accept(id), onSuccess: () => { toast.success("It's yours. Pick it up from the seller."); refresh(); }, onError: (e) => { toast.error(errorMessage(e)); refresh(); } });
  const decline = useMutation({ mutationFn: (id: number) => api.dispatch.decline(id), onSuccess: refresh, onError: (e) => toast.error(errorMessage(e)) });
  const pickup = useMutation({ mutationFn: (id: number) => api.dispatch.pickup(id), onSuccess: () => { toast.success("Marked as picked up."); refresh(); }, onError: (e) => toast.error(errorMessage(e)) });
  const [delivering, setDelivering] = useState<OrderDelivery | null>(null);

  if (jobs.isPending) return <Skeleton className="h-40 w-full" />;
  if (jobs.isError) return <ErrorState message="We couldn't load your jobs." onRetry={() => jobs.refetch()} />;
  const active = jobs.data.mine.filter((j) => j.status === "accepted" || j.status === "picked_up");
  const done = jobs.data.mine.filter((j) => j.status === "delivered");
  return (
    <div className="space-y-4">
      {active.length === 0 && jobs.data.open.length === 0 && (
        <Card>
          <p className="text-sm text-muted-foreground">No jobs right now. New delivery jobs appear here as soon as buyers pay. This page checks for new ones every few seconds.</p>
        </Card>
      )}
      {active.map((job) => (
        <Card key={job.id}>
          <h3 className="font-semibold">{job.listing_title || `Order #${job.order}`}</h3>
          <p className="text-sm font-medium text-primary">{job.status_label}</p>
          <p className="mt-2 font-semibold">You earn {naira(job.you_earn ?? "0")}</p>
          {job.pickup && <p className="mt-2 text-sm">Collect from {job.pickup_area.name}: {job.pickup.name} {job.pickup.phone}</p>}
          {job.dropoff && (
            <p className="text-sm">
              Deliver to {job.dropoff_area.name}: {job.dropoff.note}. Buyer: {job.dropoff.name} {job.dropoff.phone}
            </p>
          )}
          <div className="mt-3 flex gap-2">
            {job.can_pick_up && <Button loading={pickup.isPending} onClick={() => pickup.mutate(job.id)}>I've picked it up</Button>}
            {job.can_deliver && <Button onClick={() => setDelivering(job)}><Camera size={15} /> Confirm delivery</Button>}
          </div>
        </Card>
      ))}
      {jobs.data.open.length > 0 && <h2 className="font-display text-lg font-bold">New jobs. First to accept gets it</h2>}
      {jobs.data.open.map((job) => (
        <Card key={job.id}>
          <h3 className="font-semibold">{job.listing_title || "Delivery job"}</h3>
          <p>
            {job.pickup_area.name} to {job.dropoff_area.name}
          </p>
          <p className="mt-1 font-semibold text-primary">You earn {naira(job.you_earn)}</p>
          {job.state === "already_accepted" ? (
            <p className="mt-2 text-sm text-muted-foreground">Already accepted by another driver</p>
          ) : (
            <div className="mt-3 flex gap-2">
              <Button loading={accept.isPending} onClick={() => accept.mutate(job.id)}>Accept</Button>
              <Button variant="secondary" onClick={() => decline.mutate(job.id)}>Decline</Button>
            </div>
          )}
        </Card>
      ))}
      {done.length > 0 && (
        <Card title="Completed">
          <ul className="space-y-1 text-sm">
            {done.slice(0, 10).map((j) => (
              <li key={j.id}>
                Order #{j.order}: {j.pickup_area.name} to {j.dropoff_area.name}, you earned {naira(j.you_earn ?? "0")}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <DeliverModal job={delivering} onClose={() => setDelivering(null)} onDone={refresh} />
    </div>
  );
}

function DeliverModal({ job, onClose, onDone }: { job: OrderDelivery | null; onClose: () => void; onDone: () => void }) {
  const [code, setCode] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const deliver = useMutation({
    mutationFn: () => api.dispatch.deliver(job!.id, code, photo!),
    onSuccess: () => {
      toast.success("Delivered. Your pay is on its way.");
      setCode("");
      setPhoto(null);
      onDone();
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  return (
    <Modal open={!!job} onClose={onClose} title="Confirm delivery">
      <p className="mb-3 text-sm text-muted-foreground">Ask the buyer for their 6-digit handover code, only once they are holding the item. Then take a photo as proof.</p>
      <Field label="Buyer's code">
        <Input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="6 digits" />
      </Field>
      <Field label="Photo of the delivered item" className="mt-3">
        <input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
      </Field>
      <Button className="mt-4 w-full" loading={deliver.isPending} disabled={code.length !== 6 || !photo} onClick={() => deliver.mutate()}>
        Confirm delivery
      </Button>
    </Modal>
  );
}

function Prices() {
  const queryClient = useQueryClient();
  const routes = useQuery({ queryKey: ["driver-routes"], queryFn: api.dispatch.routes });
  const [from, setFrom] = useState<Area | null>(null);
  const [to, setTo] = useState<Area | null>(null);
  const [price, setPrice] = useState("");
  const add = useMutation({
    mutationFn: () => api.dispatch.addRoute({ from_area: from!.id, to_area: to!.id, price }),
    onSuccess: () => {
      toast.success("Price saved.");
      setPrice("");
      queryClient.invalidateQueries({ queryKey: ["driver-routes"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.dispatch.deleteRoute(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["driver-routes"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });
  return (
    <div className="space-y-4">
      <Card title="Add a trip">
        <p className="mb-3 text-sm text-muted-foreground">Set one fixed price for each trip you do, for example from Ewet Housing to Aka Road. Buyers see this exact price. Choropia keeps 2.5% of each delivery fee.</p>
        <div className="space-y-3">
          <Field label="From"><AreaSelect value={from?.id ?? null} onChange={setFrom} /></Field>
          <Field label="To"><AreaSelect value={to?.id ?? null} onChange={setTo} /></Field>
          <Field label="Price (₦)"><Input value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" /></Field>
          <Button loading={add.isPending} disabled={!from || !to || !price} onClick={() => add.mutate()}>
            <MapPin size={15} /> Save price
          </Button>
        </div>
      </Card>
      <Card title="Your prices">
        {routes.data?.filter((r) => r.is_active !== false).length ? (
          <ul className="divide-y divide-border">
            {routes.data!.filter((r) => r.is_active !== false).map((r) => (
              <li key={r.id} className="flex items-center justify-between py-3">
                <span>
                  {r.from_area.name} → {r.to_area.name}
                  <span className="ml-2 font-semibold text-primary">{naira(r.price)}</span>
                </span>
                <Button variant="secondary" onClick={() => remove.mutate(r.id)}>Remove</Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No prices yet. Sellers can only choose you once you have prices.</p>
        )}
      </Card>
    </div>
  );
}

function Account({ profile }: { profile: DriverMe }) {
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: (available: boolean) => api.dispatch.setAvailable(available),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["driver-me"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });
  return (
    <Card title={profile.full_name}>
      <p className="text-sm">
        {VEHICLES.find(([v]) => v === profile.vehicle_type)?.[1]} {profile.plate_number}
      </p>
      <p className="text-sm text-muted-foreground">
        Phone {profile.phone} · WhatsApp {profile.whatsapp}
      </p>
      <label className="mt-4 flex items-center gap-3 text-sm">
        <input type="checkbox" checked={profile.available} onChange={(e) => toggle.mutate(e.target.checked)} />
        <span>
          <strong>Available for new jobs.</strong> Switch off to stop getting job alerts.
        </span>
      </label>
      <p className="mt-4 text-sm text-muted-foreground">You are paid by bank transfer after each delivery is confirmed. Add your bank account in the Choropia app (Profile, then Payout account).</p>
      <p className="mt-3 text-sm">
        <a className="text-primary underline" href="/legal/driver_terms/" target="_blank" rel="noreferrer">Driver Terms</a> ·{" "}
        <a className="text-primary underline" href="/legal/privacy/" target="_blank" rel="noreferrer">Privacy Policy</a>
      </p>
    </Card>
  );
}
