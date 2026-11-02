import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Landmark } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Field, Input, Select, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Where a seller or driver is paid. The bank checks the account and shows the name on it before anything is paid. */
export function PayoutAccountPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const account = useQuery({ queryKey: ["payout-account"], queryFn: api.payoutAccount });
  const banks = useQuery({ queryKey: ["banks"], queryFn: api.banks, staleTime: 60 * 60_000 });
  const [bank, setBank] = useState("");
  const [number, setNumber] = useState("");
  const [editing, setEditing] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["payout-account"] });
  const save = useMutation({
    mutationFn: () => api.savePayoutAccount(bank, number),
    onSuccess: () => {
      toast.success("Saved. Any payout that was waiting is on its way.");
      setEditing(false);
      setNumber("");
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const remove = useMutation({ mutationFn: api.deletePayoutAccount, onSuccess: refresh, onError: (err) => toast.error(errorMessage(err)) });

  if (account.isPending) return <Skeleton className="mx-auto h-48 max-w-md" />;
  const configured = account.data?.configured && !editing;
  return (
    <div className="panel editorial-enter mx-auto max-w-md p-6">
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-accent text-primary"><Landmark size={20} /></div>
      <h1 className="text-xl font-bold">Payout account</h1>
      <p className="mb-5 mt-1 text-sm text-muted-foreground">
        When a buyer confirms they received an item, your money is sent to this account automatically. Choropia keeps a small commission, shown on every listing before you post it. Delivery drivers are paid here too.
      </p>
      {user && !user.profile?.email_verified && (
        <p className="mb-4 rounded-lg bg-accent p-3 text-sm">
          Verify your email first. <Link to="/verify-email" className="font-medium text-primary underline">Enter your code</Link>
        </p>
      )}
      {configured ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-border p-4">
            <p className="font-semibold">{account.data!.account_name}</p>
            <p className="text-sm text-muted-foreground">{account.data!.bank_name} ••••{account.data!.account_last4}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>Change account</Button>
            <Button variant="secondary" loading={remove.isPending} onClick={() => remove.mutate()}>Remove</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <Field label="Bank">
            <Select value={bank} onChange={(e) => setBank(e.target.value)} required>
              <option value="">Choose your bank</option>
              {banks.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
            </Select>
          </Field>
          <Field label="Account number (10 digits)">
            <Input value={number} onChange={(e) => setNumber(e.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" required />
          </Field>
          <p className="text-sm text-muted-foreground">We check the account with your bank and show you the name on it before anything is paid.</p>
          <div className="flex gap-2">
            <Button type="submit" loading={save.isPending} disabled={!bank || number.length !== 10}>Verify and save</Button>
            {account.data?.configured && <Button type="button" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>}
          </div>
        </form>
      )}
    </div>
  );
}
