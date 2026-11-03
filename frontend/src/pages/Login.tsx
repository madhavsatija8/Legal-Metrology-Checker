import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button, ErrorNote, Field, TextInput } from "../components/ui";
import { CheckCircle2, Lock, Mail, ScanLine, ShieldCheck } from "lucide-react";

const HIGHLIGHTS = [
  { icon: ScanLine, text: "Scan a label photo and auto-extract every mandatory declaration" },
  { icon: ShieldCheck, text: "Checked against the Legal Metrology (Packaged Commodities) Rules, 2011" },
  { icon: CheckCircle2, text: "Track violations from finding to resolution" },
];

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/products");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't sign in — check your connection to the API.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-white lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-action/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-72 w-72 rounded-full bg-action/20 blur-3xl" />
        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-action shadow-pop">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="font-serif text-lg font-bold">Compliance Register</span>
        </div>
        <div className="relative space-y-6">
          <h1 className="font-serif text-3xl font-bold leading-tight">
            Label compliance checks, <br /> field-ready.
          </h1>
          <div className="space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-start gap-3 text-sm text-white/75">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-action" />
                <span>{text}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-white/40">Legal Metrology (Packaged Commodities) Rules, 2011</p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center bg-paper px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-action text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <p className="font-serif text-xl font-bold text-ink">Compliance Register</p>
            <p className="text-sm text-ink-soft">Legal Metrology (Packaged Commodities) Rules, 2011</p>
          </div>
          <div className="mb-6 hidden lg:block">
            <p className="font-serif text-2xl font-bold text-ink">Welcome back</p>
            <p className="mt-1 text-sm text-ink-soft">Sign in to continue to your workspace.</p>
          </div>

          <div className="rounded-2xl border border-rule bg-paper-raised p-6 shadow-raised">
            <form onSubmit={handleSubmit} className="space-y-4">
              <Field label="Email">
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
                  <TextInput
                    type="email"
                    required
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="inspector@metrology.gov.in"
                    className="pl-9"
                  />
                </div>
              </Field>
              <Field label="Password">
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
                  <TextInput
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </Field>
              <ErrorNote>{error}</ErrorNote>
              <Button type="submit" disabled={submitting} className="w-full justify-center py-2.5">
                {submitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </div>
          <p className="mt-4 text-center text-xs text-ink-soft">
            Use a seeded account, e.g. <span className="rounded bg-paper px-1 py-0.5 font-mono">inspector@metrology.gov.in</span>{" "}
            / <span className="rounded bg-paper px-1 py-0.5 font-mono">inspector123</span>
          </p>
        </div>
      </div>
    </div>
  );
}
