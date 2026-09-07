import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button, ErrorNote, Field, Panel, TextInput } from "../components/ui";

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
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="font-serif text-2xl font-semibold text-ink">Compliance Register</p>
          <p className="mt-1 text-sm text-ink-soft">Legal Metrology (Packaged Commodities) Rules, 2011</p>
        </div>
        <Panel>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Email">
              <TextInput
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="inspector@metrology.gov.in"
              />
            </Field>
            <Field label="Password">
              <TextInput
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <ErrorNote>{error}</ErrorNote>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Panel>
        <p className="mt-4 text-center text-xs text-ink-soft">
          Use a seeded account, e.g. <span className="font-mono">inspector@metrology.gov.in</span> /{" "}
          <span className="font-mono">inspector123</span>
        </p>
      </div>
    </div>
  );
}
