import { useEffect, useState } from "react";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { RuleVersion } from "../lib/types";
import { Button, EmptyState, ErrorNote, Panel, SectionHeading } from "../components/ui";

export function RuleVersions() {
  const [versions, setVersions] = useState<RuleVersion[]>([]);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);

  function load() {
    api
      .listRuleVersions()
      .then(setVersions)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load rule versions."));
  }

  useEffect(load, []);

  async function handleSync() {
    setSyncing(true);
    setError("");
    try {
      await api.syncRuleVersionFromFile();
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't sync rules/legal_metrology_rules.json.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Panel>
      <SectionHeading
        action={
          <Button onClick={handleSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync from rules file"}
          </Button>
        }
      >
        Rule versions
      </SectionHeading>
      <ErrorNote>{error}</ErrorNote>
      <p className="mb-4 text-sm text-ink-soft">
        New scans are stamped with whichever version is active, so historical reports stay accurate after an
        amendment. Syncing re-reads <span className="font-mono">rules/legal_metrology_rules.json</span> and activates
        it only if its content hash has changed.
      </p>
      {versions.length === 0 ? (
        <EmptyState>No rule versions registered yet.</EmptyState>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-soft">
              <th className="py-2 font-medium">Label</th>
              <th className="py-2 font-medium">Hash</th>
              <th className="py-2 font-medium">Activated</th>
              <th className="py-2 font-medium">Active</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.id} className="border-b border-rule/60">
                <td className="py-2">{v.version_label}</td>
                <td className="py-2 font-mono text-xs text-ink-soft">{v.source_file_hash.slice(0, 12)}</td>
                <td className="py-2 text-ink-soft">{new Date(v.activated_at).toLocaleString()}</td>
                <td className="py-2">
                  {v.is_active ? <span className="text-verified">Active</span> : <span className="text-ink-soft">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
