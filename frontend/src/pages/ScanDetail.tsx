import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { ExtractedField, Scan } from "../lib/types";
import { MatchBadge, SeverityBadge, StatusBadge } from "../components/Badge";
import { RoleGate } from "../components/RoleGate";
import { Button, EmptyState, ErrorNote, Panel, SectionHeading, TextInput } from "../components/ui";

function fieldLabel(key: string): string {
  return key.replace(/_/g, " ");
}

function ExtractedFieldRow({ name, field }: { name: string; field: ExtractedField }) {
  const extras = Object.entries(field).filter(
    ([k, v]) => !["matched", "source_line", "pixel_height"].includes(k) && v !== null && v !== undefined && v !== ""
  );
  return (
    <div className="border-b border-rule/60 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium capitalize text-ink">{fieldLabel(name)}</span>
        <MatchBadge matched={field.matched} />
      </div>
      {(field.source_line || extras.length > 0 || field.pixel_height) && (
        <dl className="mt-1.5 grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 text-xs text-ink-soft">
          {extras.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="capitalize">{fieldLabel(k)}</dt>
              <dd className="text-ink">{String(v)}</dd>
            </div>
          ))}
          {field.pixel_height != null && (
            <>
              <dt>Glyph height</dt>
              <dd className="font-mono text-ink">{field.pixel_height.toFixed(1)} px</dd>
            </>
          )}
          {field.source_line && (
            <>
              <dt>OCR line</dt>
              <dd className="italic text-ink">"{field.source_line}"</dd>
            </>
          )}
        </dl>
      )}
    </div>
  );
}

export function ScanDetail() {
  const { id } = useParams<{ id: string }>();
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState<"pdf" | "docx" | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    if (!id) return;
    try {
      setScan(await api.getScan(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this scan.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setBusy(true);
    setError("");
    try {
      setScan(await api.uploadScanImage(id, file));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleEvaluate() {
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      setScan(await api.evaluateScan(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't re-run the compliance check.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReprocess() {
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      setScan(await api.reprocessScan(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reprocessing failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResolveViolation(violationId: string, note: string) {
    if (!scan) return;
    try {
      const updated = await api.updateViolation(violationId, { is_resolved: true, resolution_note: note });
      setScan({ ...scan, violations: scan.violations.map((v) => (v.id === updated.id ? updated : v)) });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't resolve the violation.");
    }
  }

  async function handleDownloadReport(format: "pdf" | "docx") {
    if (!id) return;
    setReportBusy(format);
    setError("");
    try {
      await api.downloadScanReport(id, format);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't generate the report.");
    } finally {
      setReportBusy(null);
    }
  }

  if (!scan) return error ? <ErrorNote>{error}</ErrorNote> : <EmptyState>Loading…</EmptyState>;

  const fields = scan.extracted_fields?.fields;
  const extractionError = (scan.extracted_fields as { error?: string } | undefined)?.error;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-ink-soft">
            Scan for <Link to={`/products/${scan.product_id}`} className="text-action hover:underline">product</Link>
          </p>
          <p className="font-serif text-lg font-semibold text-ink">{new Date(scan.created_at).toLocaleString()}</p>
        </div>
        <div className="flex items-center gap-3">
          {fields && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => handleDownloadReport("pdf")} disabled={reportBusy !== null}>
                {reportBusy === "pdf" ? "Generating…" : "Download PDF"}
              </Button>
              <Button variant="secondary" onClick={() => handleDownloadReport("docx")} disabled={reportBusy !== null}>
                {reportBusy === "docx" ? "Generating…" : "Download Word"}
              </Button>
            </div>
          )}
          <StatusBadge status={scan.status} />
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      {extractionError && (
        <div className="rounded-md border border-seal/30 bg-seal/5 p-4 text-sm text-seal">
          <p className="font-medium">OCR Extraction Notice:</p>
          <p className="mt-1 font-mono text-xs">{extractionError}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <div className="flex items-center justify-between mb-2">
            <SectionHeading>Label image</SectionHeading>
            {scan.image_path && (
              <Button variant="secondary" onClick={handleReprocess} disabled={busy}>
                {busy ? "Processing…" : "Run OCR & Extract"}
              </Button>
            )}
          </div>
          {scan.image_path ? (
            <img
              src={api.scanImageUrl(scan.image_path)}
              alt="Uploaded label"
              className="mb-4 max-h-96 w-full rounded-sm border border-rule object-contain"
            />
          ) : (
            <EmptyState>No image uploaded yet.</EmptyState>
          )}
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleUpload} disabled={busy} className="text-sm" />
        </Panel>

        <Panel>
          <SectionHeading>Calibration &amp; evaluation</SectionHeading>
          <RoleGate roles={["supervisor", "admin"]}>
            <CalibrationForm scan={scan} onSaved={setScan} />
          </RoleGate>
          <p className="mt-3 text-xs text-ink-soft">
            {scan.calibration_px_per_mm
              ? `Calibrated at ${scan.calibration_px_per_mm} px/mm — font-size checks use this to convert glyph height.`
              : "No calibration set — font-size/readability checks will be skipped until a supervisor sets pixels-per-mm."}
          </p>
          <div className="mt-4">
            <Button variant="secondary" onClick={handleEvaluate} disabled={busy || !scan.extracted_fields}>
              {busy ? "Working…" : "Re-run compliance check"}
            </Button>
          </div>
          {scan.compliance_review && (
            <div className="mt-4 border-t border-rule pt-3 text-sm">
              {scan.compliance_review.exempt && (
                <p className="text-verified">Exempt: {scan.compliance_review.exemption_reason}</p>
              )}
              {scan.compliance_review.review_items.length > 0 && (
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-ink-soft">Needs manual review</p>
                  <ul className="list-inside list-disc space-y-1 text-ink-soft">
                    {scan.compliance_review.review_items.map((ri, i) => (
                      <li key={i}>
                        <span className="font-medium text-ink">{ri.category}:</span> {ri.note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>

      <Panel>
        <SectionHeading>Extracted declarations</SectionHeading>
        {!fields ? (
          <div className="space-y-3">
            <EmptyState>Upload a label image or click "Run OCR & Extract" to process declarations.</EmptyState>
            {scan.image_path && (
              <div className="flex justify-center">
                <Button onClick={handleReprocess} disabled={busy}>
                  {busy ? "Processing OCR…" : "Run OCR & Extract Declarations"}
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div>
            {Object.entries(fields).map(([name, field]) => (
              <ExtractedFieldRow key={name} name={name} field={field} />
            ))}
          </div>
        )}
      </Panel>

      <Panel>
        <SectionHeading>Violations ({scan.violations.length})</SectionHeading>
        {scan.violations.length === 0 ? (
          <EmptyState>No violations recorded on this scan.</EmptyState>
        ) : (
          <ul className="space-y-3">
            {scan.violations.map((v) => (
              <li key={v.id} className="border-b border-rule/60 pb-3 last:border-0">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="mb-1 flex items-center gap-2">
                      <SeverityBadge severity={v.severity} />
                      {v.citation && <span className="text-xs text-ink-soft">{v.citation}</span>}
                      {v.needs_review && <span className="text-xs text-caution">low-confidence match</span>}
                    </div>
                    <p className="text-sm text-ink">{v.description}</p>
                    {v.is_resolved && v.resolution_note && (
                      <p className="mt-1 text-xs text-verified">Resolved: {v.resolution_note}</p>
                    )}
                  </div>
                  {!v.is_resolved && (
                    <ResolveButton onResolve={(note) => handleResolveViolation(v.id, note)} />
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function CalibrationForm({ scan, onSaved }: { scan: Scan; onSaved: (s: Scan) => void }) {
  const [value, setValue] = useState(scan.calibration_px_per_mm?.toString() ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const num = parseFloat(value);
    if (Number.isNaN(num) || num <= 0) {
      setError("Enter a positive number of pixels per millimetre.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      onSaved(await api.updateScan(scan.id, { calibration_px_per_mm: num }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save calibration.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2">
      <div className="flex-1">
        <label className="mb-1 block text-sm text-ink-soft">Pixels per mm (from a reference object)</label>
        <TextInput
          type="number"
          step="0.01"
          min="0"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. 11.8"
        />
      </div>
      <Button type="submit" variant="secondary" disabled={submitting}>
        {submitting ? "Saving…" : "Set"}
      </Button>
      {error && <span className="text-xs text-seal">{error}</span>}
    </form>
  );
}

function ResolveButton({ onResolve }: { onResolve: (note: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");

  if (!editing) {
    return (
      <Button variant="secondary" onClick={() => setEditing(true)}>
        Resolve
      </Button>
    );
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <TextInput
        placeholder="How was this corrected?"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        className="w-56"
      />
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => setEditing(false)}>
          Cancel
        </Button>
        <Button onClick={() => onResolve(note)} disabled={!note}>
          Confirm
        </Button>
      </div>
    </div>
  );
}
