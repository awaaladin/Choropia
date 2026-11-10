import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { KeyRound, Mail, ShieldCheck } from "lucide-react";
import { Button } from "@/components/Button";
import { api, ApiError } from "@/lib/api";
import type { PinStatus } from "@/lib/types";
import { InlineError } from "./InlineError";
import { fade, spring, useCalmMotion } from "./motion";
import { PinPad } from "./PinPad";

type Step = "proof" | "choose" | "confirm";

/**
 * Set a first transaction PIN, or replace a forgotten one. Replacing needs proof: the account password, or a 6-digit
 * code emailed to the person (for accounts that sign in with Google and have no password).
 */
export function PinSetupFlow({ mode, length = 4, onDone }: { mode: "setup" | "reset"; length?: number; onDone: (status: PinStatus) => void }) {
  const calm = useCalmMotion();
  const [step, setStep] = useState<Step>(mode === "reset" ? "proof" : "choose");
  const [proof, setProof] = useState<{ password?: string; email_code?: string }>({});
  const [proofKind, setProofKind] = useState<"password" | "email">("password");
  const [proofText, setProofText] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [errorTick, setErrorTick] = useState(0);
  const [busy, setBusy] = useState(false);

  const fail = (message: string) => {
    setError(message);
    setErrorTick((t) => t + 1);
  };

  const submit = async (pin: string) => {
    setBusy(true);
    setError(null);
    try {
      const status = await api.setPin({ pin, ...proof });
      onDone(status);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't save your PIN. Check your connection and try again.";
      // A weak PIN or wrong proof: start again from the right step.
      if (e instanceof ApiError && /password|code/i.test(message)) setStep("proof");
      else setStep("choose");
      setFirst("");
      setSecond("");
      fail(message);
    } finally {
      setBusy(false);
    }
  };

  const sendCode = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.pinResetCode();
      setCodeSent(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send the code. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const enter = calm ? { opacity: 0 } : { opacity: 0, x: 24 };
  const leave = calm ? { opacity: 0 } : { opacity: 0, x: -24 };

  return (
    <div className="pb-2">
      <AnimatePresence mode="wait" initial={false}>
        {step === "proof" && (
          <motion.div key="proof" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
            <div className="flex items-start gap-3 rounded-o-md bg-o-surface p-4">
              <KeyRound size={20} strokeWidth={1.75} className="mt-0.5 shrink-0 text-o-accent" aria-hidden="true" />
              <p className="text-sm text-o-muted">To set a new PIN, first prove it's you.</p>
            </div>
            <div className="mt-4 flex gap-2" role="radiogroup" aria-label="How to prove it's you">
              {(["password", "email"] as const).map((kind) => (
                <button
                  key={kind}
                  type="button"
                  role="radio"
                  aria-checked={proofKind === kind}
                  onClick={() => {
                    setProofKind(kind);
                    setProofText("");
                  }}
                  className={
                    "min-h-11 flex-1 rounded-o-sm border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent " +
                    (proofKind === kind ? "border-o-accent bg-o-tide text-o-tide-fg" : "border-o-hairline text-o-muted hover:bg-o-surface")
                  }
                >
                  {kind === "password" ? "My password" : "Email me a code"}
                </button>
              ))}
            </div>
            <form
              className="mt-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!proofText.trim()) return;
                setProof(proofKind === "password" ? { password: proofText } : { email_code: proofText.trim() });
                setError(null);
                setStep("choose");
              }}
            >
              {proofKind === "email" && !codeSent ? (
                <Button type="button" onClick={sendCode} loading={busy} className="min-h-11 w-full">
                  <Mail size={16} strokeWidth={1.75} aria-hidden="true" /> Send me a code
                </Button>
              ) : (
                <>
                  <label className="text-sm font-medium" htmlFor="pin-proof">
                    {proofKind === "password" ? "Password" : "6-digit code from your email"}
                  </label>
                  <input
                    id="pin-proof"
                    type={proofKind === "password" ? "password" : "text"}
                    inputMode={proofKind === "password" ? undefined : "numeric"}
                    autoComplete={proofKind === "password" ? "current-password" : "one-time-code"}
                    value={proofText}
                    onChange={(e) => setProofText(e.target.value)}
                    className="mt-1.5 min-h-11 w-full rounded-o-sm border border-o-hairline bg-o-raised px-3 text-o-text outline-none focus:ring-2 focus:ring-o-accent"
                  />
                  <Button type="submit" className="mt-3 min-h-11 w-full" disabled={!proofText.trim()}>
                    Continue
                  </Button>
                </>
              )}
            </form>
          </motion.div>
        )}

        {step === "choose" && (
          <motion.div key="choose" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
            <p className="mb-2 text-center text-sm text-o-muted">
              {mode === "setup"
                ? "You'll use this PIN to approve offers. Choropia never asks for it."
                : "Choose a new PIN."}{" "}
              Avoid 1234 or repeated digits.
            </p>
            <PinPad
              length={length}
              label={`Choose a ${length}-digit PIN`}
              value={first}
              onChange={(v) => {
                setFirst(v);
                if (v) setError(null);
              }}
              onComplete={() => setStep("confirm")}
              errorTick={errorTick}
              error={Boolean(error)}
            />
          </motion.div>
        )}

        {step === "confirm" && (
          <motion.div key="confirm" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
            <PinPad
              length={length}
              label="Enter it again to confirm"
              value={second}
              onChange={setSecond}
              disabled={busy}
              onComplete={(v) => {
                if (v !== first) {
                  setFirst("");
                  setSecond("");
                  setStep("choose");
                  fail("Those PINs didn't match. Choose again.");
                  return;
                }
                void submit(v);
              }}
              errorTick={errorTick}
              error={Boolean(error)}
            />
            {busy && (
              <p className="mt-3 flex items-center justify-center gap-2 text-sm text-o-muted" aria-live="polite">
                <ShieldCheck size={16} strokeWidth={1.75} aria-hidden="true" /> Saving your PIN…
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      <InlineError message={error} />
    </div>
  );
}
