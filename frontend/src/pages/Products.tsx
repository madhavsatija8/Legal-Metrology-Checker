import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Product } from "../lib/types";
import { Button, EmptyState, ErrorNote, Field, Panel, SectionHeading, TextInput } from "../components/ui";

export function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);

  async function load(query?: string) {
    setLoading(true);
    setError("");
    try {
      setProducts(await api.listProducts(query));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load products.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    load(q);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <form onSubmit={handleSearch} className="flex flex-1 gap-2">
          <TextInput
            placeholder="Search by name or brand…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="max-w-sm"
          />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "New product"}</Button>
      </div>

      {showForm && (
        <Panel>
          <NewProductForm
            onCreated={(p) => {
              setProducts((prev) => [p, ...prev]);
              setShowForm(false);
            }}
          />
        </Panel>
      )}

      <Panel>
        <SectionHeading>Products</SectionHeading>
        <ErrorNote>{error}</ErrorNote>
        {loading ? (
          <EmptyState>Loading…</EmptyState>
        ) : products.length === 0 ? (
          <EmptyState>No products yet — add one above to start a scan against it.</EmptyState>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-soft">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Brand</th>
                <th className="py-2 font-medium">Category</th>
                <th className="py-2 font-medium">Manufacturer</th>
                <th className="py-2 font-medium">Imported</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-rule/60 hover:bg-paper">
                  <td className="py-2">
                    <Link to={`/products/${p.id}`} className="text-action hover:underline">
                      {p.name}
                    </Link>
                  </td>
                  <td className="py-2 text-ink-soft">{p.brand ?? "—"}</td>
                  <td className="py-2 text-ink-soft">{p.category ?? "—"}</td>
                  <td className="py-2 text-ink-soft">{p.manufacturer_name ?? "—"}</td>
                  <td className="py-2 text-ink-soft">{p.is_imported ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function NewProductForm({ onCreated }: { onCreated: (p: Product) => void }) {
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [isImported, setIsImported] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const product = await api.createProduct({
        name,
        brand: brand || undefined,
        category: category || undefined,
        manufacturer_name: manufacturer || undefined,
        is_imported: isImported,
      });
      onCreated(product);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create product.");
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
      <label className="flex items-center gap-2 text-sm text-ink-soft sm:col-span-2">
        <input type="checkbox" checked={isImported} onChange={(e) => setIsImported(e.target.checked)} />
        Imported product (adds the country-of-origin declaration requirement)
      </label>
      <div className="sm:col-span-2">
        <ErrorNote>{error}</ErrorNote>
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : "Save product"}
        </Button>
      </div>
    </form>
  );
}
