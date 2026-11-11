import { ArrowRight, Check, MapPin, MessageCircle, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { PublicShell } from "@/components/PublicShell";
import { Field, Input, Select, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useReveal } from "@/lib/useReveal";

/** Writes straight to the Choropia team: they are emailed the moment you send it. */
function ContactForm() {
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setSending(true);
    try {
      await api.sendContact({
        name: String(data.get("name") ?? ""),
        email: String(data.get("email") ?? ""),
        topic: String(data.get("topic") ?? "question"),
        message: String(data.get("message") ?? ""),
        website: String(data.get("website") ?? ""),
      });
      setSent(true);
      form.reset();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <div className="panel mt-12 flex items-start gap-3 p-6">
        <Check className="mt-0.5 text-success" size={20} />
        <div>
          <h2 className="font-semibold">We got your message</h2>
          <p className="mt-1 text-sm text-muted-foreground">We have emailed you a copy, and we will reply as soon as we can.</p>
        </div>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="panel mt-12 max-w-xl space-y-3 p-6">
      <h2 className="font-semibold">Write to us</h2>
      <p className="text-sm text-muted-foreground">Questions, problems, or something that doesn't feel right. A real person reads every message.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Your name">
          <Input name="name" required maxLength={120} defaultValue={user ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() : ""} />
        </Field>
        <Field label="Email to reply to">
          <Input name="email" type="email" required defaultValue={user?.email ?? ""} />
        </Field>
      </div>
      <Field label="What is this about?">
        <Select name="topic" defaultValue="question">
          <option value="question">A question</option>
          <option value="problem">A problem or complaint</option>
          <option value="report">Reporting someone or something</option>
          <option value="other">Something else</option>
        </Select>
      </Field>
      <Field label="Message">
        <Textarea name="message" rows={5} required minLength={10} maxLength={3000} />
      </Field>
      {/* Hidden from people; bots fill it in and are ignored. */}
      <input name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
      <Button type="submit" loading={sending}>
        Send message
      </Button>
    </form>
  );
}

export function ContactPage() {
  useReveal();
  return (
    <PublicShell>
      <section className="mx-auto max-w-[1400px] px-5 py-14 lg:px-8 lg:py-20">
        <p className="page-enter eyebrow">LET'S TALK</p>
        <h1 className="page-enter mt-4 text-4xl font-semibold sm:text-6xl">
          Good conversations
          <br />
          start here.
        </h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">
          Most questions have a faster answer than a contact form — here's where to take them.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          <div data-reveal className="border-t border-border py-6">
            <MessageCircle className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">A question about an item or order?</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">The seller is the best person to ask about condition, availability, and pickup — message them directly.</p>
            <Link to="/messages" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Open messages <ArrowRight size={15} />
            </Link>
          </div>
          <div data-reveal className="border-t border-border py-6">
            <ShieldAlert className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">Something wrong with an order?</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">Open a dispute right from the order page — a moderator reviews it before escrow is released.</p>
            <Link to="/orders" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Go to your orders <ArrowRight size={15} />
            </Link>
          </div>
          <div data-reveal className="border-t border-border py-6">
            <MapPin className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">Starting in Uyo</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">Akwa Ibom, Nigeria. Open to buyers and sellers across Nigeria.</p>
            <Link to="/how-it-works" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Find an answer in our guide <ArrowRight size={15} />
            </Link>
          </div>
        </div>

        <ContactForm />
      </section>
    </PublicShell>
  );
}
