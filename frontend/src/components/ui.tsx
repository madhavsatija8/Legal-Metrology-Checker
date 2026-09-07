import type { ButtonHTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-sm border border-rule bg-paper-raised p-5 ${className}`}>{children}</div>;
}

export function SectionHeading({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between border-b border-rule pb-2">
      <h2 className="font-serif text-lg font-semibold text-ink">{children}</h2>
      {action}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-ink-soft">{label}</span>
      {children}
    </label>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-sm border border-rule bg-white px-3 py-1.5 text-sm text-ink outline-none focus:border-action ${props.className ?? ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-sm border border-rule bg-white px-3 py-1.5 text-sm text-ink outline-none focus:border-action ${props.className ?? ""}`}
    />
  );
}

type ButtonVariant = "primary" | "secondary" | "danger";

const VARIANT_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-action text-white hover:bg-[#234a63] disabled:bg-ink-soft",
  secondary: "border border-rule bg-white text-ink hover:bg-paper disabled:text-ink-soft",
  danger: "border border-seal bg-white text-seal hover:bg-seal-soft disabled:text-ink-soft",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={`rounded-sm px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_STYLES[variant]} ${className}`}
    />
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p className="rounded-sm border-l-2 border-seal bg-seal-soft px-3 py-2 text-sm text-seal" role="alert">
      {children}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-ink-soft">{children}</p>;
}

export function LabelText(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm text-ink-soft ${props.className ?? ""}`} />;
}
