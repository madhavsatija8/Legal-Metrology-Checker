import type { ScanStatus, ViolationSeverity } from "../lib/types";

// Severity/status are shown as a small tag with color carried on the
// left border (like a case-file tab), not a fully-filled pill — keeps
// the palette quiet and reads as a status marker, not decoration.
const SEVERITY_STYLES: Record<ViolationSeverity, string> = {
  critical: "border-seal bg-seal-soft text-seal",
  major: "border-caution bg-caution-soft text-caution",
  minor: "border-ink-soft bg-paper-raised text-ink-soft",
};

export function SeverityBadge({ severity }: { severity: ViolationSeverity }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border-l-2 px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}

const STATUS_STYLES: Record<ScanStatus, string> = {
  pending: "border-ink-soft bg-paper-raised text-ink-soft",
  processing: "border-action bg-action-soft text-action",
  review: "border-caution bg-caution-soft text-caution",
  resolved: "border-verified bg-verified-soft text-verified",
  escalated: "border-seal bg-seal-soft text-seal",
};

export function StatusBadge({ status }: { status: ScanStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border-l-2 px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

export function MatchBadge({ matched }: { matched: boolean }) {
  return matched ? (
    <span className="inline-flex items-center rounded-sm border-l-2 border-verified bg-verified-soft px-2 py-0.5 text-xs font-medium text-verified">
      found
    </span>
  ) : (
    <span className="inline-flex items-center rounded-sm border-l-2 border-seal bg-seal-soft px-2 py-0.5 text-xs font-medium text-seal">
      missing
    </span>
  );
}
