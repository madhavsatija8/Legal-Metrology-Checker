import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";
import { AlertTriangle, Search } from "lucide-react";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-rule bg-paper-raised p-6 shadow-card ${className}`}>{children}</div>
  );
}

export function SectionHeading({ children, action, subtitle }: { children: ReactNode; action?: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4 border-b border-rule pb-4">
      <div>
        <h2 className="font-serif text-lg font-semibold tracking-tight text-ink">{children}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </label>
  );
}

const controlBase =
  "w-full rounded-lg border border-rule bg-paper px-3.5 py-2 text-sm text-ink outline-none transition-shadow placeholder:text-ink-soft/70 focus:border-action focus:bg-paper-raised focus:ring-4 focus:ring-action-soft";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${controlBase} ${props.className ?? ""}`} />;
}

export function SearchInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
      <input {...props} className={`${controlBase} pl-9 ${props.className ?? ""}`} />
    </div>
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${controlBase} cursor-pointer ${props.className ?? ""}`} />;
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const VARIANT_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-action text-white shadow-sm hover:bg-[#4338CA] disabled:bg-ink-soft/50 disabled:shadow-none",
  secondary: "border border-rule bg-paper-raised text-ink hover:border-action/40 hover:bg-action-soft disabled:text-ink-soft",
  danger: "border border-seal/30 bg-seal-soft text-seal hover:bg-seal hover:text-white disabled:text-ink-soft disabled:bg-transparent",
  ghost: "text-ink-soft hover:bg-paper hover:text-ink",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${VARIANT_STYLES[variant]} ${className}`}
    />
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p
      className="flex items-start gap-2 rounded-lg border border-seal/20 bg-seal-soft px-3.5 py-2.5 text-sm text-seal"
      role="alert"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function EmptyState({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-14 text-center">
      {icon && <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-full bg-paper text-ink-soft">{icon}</div>}
      <p className="text-sm text-ink-soft">{children}</p>
    </div>
  );
}

export function LabelText(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm text-ink-soft ${props.className ?? ""}`} />;
}

/** Small KPI tile for dashboard-style summaries (Products, Scans landing pages). */
export function StatCard({
  label,
  value,
  icon,
  tone = "action",
}: {
  label: string;
  value: string | number;
  icon: ReactNode;
  tone?: "action" | "seal" | "verified" | "caution";
}) {
  const toneStyles: Record<string, string> = {
    action: "bg-action-soft text-action",
    seal: "bg-seal-soft text-seal",
    verified: "bg-verified-soft text-verified",
    caution: "bg-caution-soft text-caution",
  };
  return (
    <div className="flex items-center gap-3.5 rounded-2xl border border-rule bg-paper-raised p-4 shadow-card">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${toneStyles[tone]}`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-2xl font-bold leading-tight tracking-tight text-ink">{value}</p>
        <p className="truncate text-xs font-medium text-ink-soft">{label}</p>
      </div>
    </div>
  );
}
