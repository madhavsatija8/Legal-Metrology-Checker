import type { ScanStatus, ViolationSeverity } from "../lib/types";
import { AlertOctagon, AlertTriangle, CheckCircle2, Circle, Clock, Info, Loader2, ShieldAlert, XCircle } from "lucide-react";

// Severity/status are shown as a small solid pill with an icon — reads
// as a real status chip, not a plain text label.
const SEVERITY_STYLES: Record<ViolationSeverity, string> = {
  critical: "bg-seal-soft text-seal",
  major: "bg-caution-soft text-caution",
  minor: "bg-rule/70 text-ink-soft",
};

const SEVERITY_ICON: Record<ViolationSeverity, ReactNodeIcon> = {
  critical: AlertOctagon,
  major: AlertTriangle,
  minor: Info,
};

type ReactNodeIcon = typeof AlertOctagon;

export function SeverityBadge({ severity }: { severity: ViolationSeverity }) {
  const Icon = SEVERITY_ICON[severity];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${SEVERITY_STYLES[severity]}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {severity}
    </span>
  );
}

const STATUS_STYLES: Record<ScanStatus, string> = {
  pending: "bg-rule/70 text-ink-soft",
  processing: "bg-action-soft text-action",
  review: "bg-caution-soft text-caution",
  resolved: "bg-verified-soft text-verified",
  escalated: "bg-seal-soft text-seal",
};

const STATUS_ICON: Record<ScanStatus, ReactNodeIcon> = {
  pending: Circle,
  processing: Loader2,
  review: Clock,
  resolved: CheckCircle2,
  escalated: ShieldAlert,
};

export function StatusBadge({ status }: { status: ScanStatus }) {
  const Icon = STATUS_ICON[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${STATUS_STYLES[status]}`}
    >
      <Icon className={`h-3.5 w-3.5 ${status === "processing" ? "animate-spin" : ""}`} />
      {status}
    </span>
  );
}

export function MatchBadge({ matched }: { matched: boolean }) {
  return matched ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-verified-soft px-2.5 py-1 text-xs font-semibold text-verified">
      <CheckCircle2 className="h-3.5 w-3.5" />
      found
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-seal-soft px-2.5 py-1 text-xs font-semibold text-seal">
      <XCircle className="h-3.5 w-3.5" />
      missing
    </span>
  );
}
