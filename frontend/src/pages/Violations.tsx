import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Violation, ViolationSeverity } from "../lib/types";
import { SeverityBadge } from "../components/Badge";
import { EmptyState, ErrorNote, Panel, SectionHeading, Select } from "../components/ui";

const SEVERITIES: ViolationSeverity[] = ["critical", "major", "minor"];

export function Violations() {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [severity, setSeverity] = useState<ViolationSeverity | "">("");
  const [resolved, setResolved] = useState<"" | "true" | "false">("false");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .listViolations({
        severity: severity || undefined,
        is_resolved: resolved === "" ? undefined : resolved === "true",
      })
      .then(setViolations)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load violations."))
      .finally(() => setLoading(false));
  }, [severity, resolved]);

  return (
    <Panel>
      <SectionHeading
        action={
          <div className="flex gap-2">
            <Select value={resolved} onChange={(e) => setResolved(e.target.value as typeof resolved)} className="w-36">
              <option value="false">Unresolved</option>
              <option value="true">Resolved</option>
              <option value="">All</option>
            </Select>
            <Select value={severity} onChange={(e) => setSeverity(e.target.value as ViolationSeverity | "")} className="w-36">
              <option value="">All severities</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
        }
      >
        Violations
      </SectionHeading>
      <ErrorNote>{error}</ErrorNote>
      {loading ? (
        <EmptyState>Loading…</EmptyState>
      ) : violations.length === 0 ? (
        <EmptyState>Nothing matches this filter.</EmptyState>
      ) : (
        <ul className="divide-y divide-rule/60">
          {violations.map((v) => (
            <li key={v.id} className="py-3">
              <div className="mb-1 flex items-center gap-2">
                <SeverityBadge severity={v.severity} />
                {v.citation && <span className="text-xs text-ink-soft">{v.citation}</span>}
                <span className="text-xs text-ink-soft">· {new Date(v.created_at).toLocaleDateString()}</span>
              </div>
              <p className="text-sm text-ink">{v.description}</p>
              <Link to={`/scans/${v.scan_id}`} className="text-xs text-action hover:underline">
                View scan →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
