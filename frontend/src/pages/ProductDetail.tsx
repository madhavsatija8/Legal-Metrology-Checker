import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Product, Scan } from "../lib/types";
import { RoleGate } from "../components/RoleGate";
import { StatusBadge } from "../components/Badge";
import { Button, EmptyState, ErrorNote, Field, Panel, SectionHeading, TextInput } from "../components/ui";

export function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [startingScan, setStartingScan] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getProduct(id).then(setProduct).catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
    api.listScans({ product_id: id }).then(setScans).catch(() => {});
  }, [id]);

  async function handleStartScan() {
    if (!id) return;
    setStartingScan(true);
    try {
      const scan = await api.createScan({ product_id: id });
      navigate(`/scans/${scan.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start a scan.");
    } finally {
      setStartingScan(false);
    }
  }

  if (error && !product) return <ErrorNote>{error}</ErrorNote>;
  if (!product) return <EmptyState>Loading…</EmptyState>;

  return (
    <div className="space-y-6">
      <Panel>
        <SectionHeading
          action={
            <RoleGate roles={["supervisor", "admin"]}>
              <Button variant="secondary" onClick={() => setEditing((s) => !s)}>
                {editing ? "Cancel" : "Edit"}
              </Button>
            </RoleGate>
          }
        >
          {product.name}
        </SectionHeading>
        {editing ? (
          <EditProductForm
            product={product}
            onSaved={(p) => {
              setProduct(p);
              setEditing(false);
            }}
          />
        ) : (
          <dl className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
            <dt className="text-ink-soft">Brand</dt>
            <dd>{product.brand ?? "—"}</dd>
            <dt className="text-ink-soft">Category</dt>
            <dd>{product.category ?? "—"}</dd>
            <dt className="text-ink-soft">Manufacturer</dt>
            <dd>{product.manufacturer_name ?? "—"}</dd>
            <dt className="text-ink-soft">Imported</dt>
            <dd>{product.is_imported ? "Yes" : "No"}</dd>
            {product.surface_treatment && (
              <>
                <dt className="text-ink-soft">Surface treatment</dt>
                <dd>{product.surface_treatment}</dd>
              </>
            )}
          </dl>
        )}
      </Panel>

      <Panel>
        <SectionHeading
          action={
            <Button onClick={handleStartScan} disabled={startingScan}>
              {startingScan ? "Starting…" : "Start new scan"}
            </Button>
          }
        >
          Scan history
        </SectionHeading>
        <ErrorNote>{error}</ErrorNote>
        {scans.length === 0 ? (
          <EmptyState>No scans yet for this product.</EmptyState>
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
    </div>
  );
}

function EditProductForm({ product, onSaved }: { product: Product; onSaved: (p: Product) => void }) {
  const [name, setName] = useState(product.name);
  const [brand, setBrand] = useState(product.brand ?? "");
  const [category, setCategory] = useState(product.category ?? "");
  const [manufacturer, setManufacturer] = useState(product.manufacturer_name ?? "");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const updated = await api.updateProduct(product.id, {
        name,
        brand: brand || undefined,
        category: category || undefined,
        manufacturer_name: manufacturer || undefined,
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save changes.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
      <Field label="Name">
        <TextInput required value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Brand">
        <TextInput value={brand} onChange={(e) => setBrand(e.target.value)} />
      </Field>
      <Field label="Category">
        <TextInput value={category} onChange={(e) => setCategory(e.target.value)} />
      </Field>
      <Field label="Manufacturer name">
        <TextInput value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} />
      </Field>
      <div className="sm:col-span-2">
        <ErrorNote>{error}</ErrorNote>
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
