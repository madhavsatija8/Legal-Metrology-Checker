import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Scan, ScanStatus } from "../lib/types";
import { StatusBadge } from "../components/Badge";
import { EmptyState, ErrorNote, Panel, SectionHeading, Select } from "../components/ui";

const STATUSES: ScanStatus[] = ["pending", "processing", "review", "resolved", "escalated"];

export function Scans() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [status, setStatus] = useState<ScanStatus | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .listScans({ status: status || undefined })
      .then(setScans)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load scans."))
      .finally(() => setLoading(false));
  }, [status]);

  return (
    <Panel>
      <SectionHeading
        action={
          <Select value={status} onChange={(e) => setStatus(e.target.value as ScanStatus | "")} className="w-40">
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        }
      >
        Scans
      </SectionHeading>
      <ErrorNote>{error}</ErrorNote>
      {loading ? (
        <EmptyState>Loading…</EmptyState>
      ) : scans.length === 0 ? (
        <EmptyState>No scans match this filter.</EmptyState>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-soft">
              <th className="py-2 font-medium">Created</th>
              <th className="py-2 font-medium">Status</th>
              <th className="py-2 font-medium">Violations</th>
            </tr>
          </thead>
          <tbody>
            {scans.map((s) => (
              <tr key={s.id} className="border-b border-rule/60 hover:bg-paper">
                <td className="py-2">
                  <Link to={`/scans/${s.id}`} className="text-action hover:underline">
                    {new Date(s.created_at).toLocaleString()}
                  </Link>
                </td>
                <td className="py-2">
                  <StatusBadge status={s.status} />
                </td>
                <td className="py-2 text-ink-soft">{s.violations.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
