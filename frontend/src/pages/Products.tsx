import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Product } from "../lib/types";
import { Button, EmptyState, ErrorNote, Field, Panel, SearchInput, SectionHeading, StatCard, TextInput } from "../components/ui";
import { Boxes, Globe2, Package, Plus, PlusCircle, RefreshCw, Tag, X } from "lucide-react";

export function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [q, setQ] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<{ inserted: number; skipped: number } | null>(null);

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

  async function handleSeed() {
    setSeeding(true);
    setSeedResult(null);
    try {
      const result = await api.seedProducts();
      setSeedResult(result);
      await load(); // Refresh the list
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Seeding failed.");
    } finally {
      setSeeding(false);
    }
  }

  const categories = useMemo(() => {
    const cats = Array.from(new Set(products.map((p) => p.category).filter(Boolean))) as string[];
    return ["All", ...cats.sort()];
  }, [products]);

  const filtered = useMemo(() => {
    if (categoryFilter === "All") return products;
    return products.filter((p) => p.category === categoryFilter);
  }, [products, categoryFilter]);

  const stats = useMemo(
    () => ({
      total: products.length,
      imported: products.filter((p) => p.is_imported).length,
      categories: new Set(products.map((p) => p.category).filter(Boolean)).size,
    }),
    [products],
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Registered products" value={stats.total} icon={<Package className="h-5 w-5" />} tone="action" />
        <StatCard label="Imported products" value={stats.imported} icon={<Globe2 className="h-5 w-5" />} tone="caution" />
        <StatCard label="Categories" value={stats.categories} icon={<Tag className="h-5 w-5" />} tone="verified" />
      </div>

      {/* Seed Banner — shown when DB is empty or after seeding */}
      {!loading && products.length === 0 && !seedResult && (
        <Panel>
          <div className="flex flex-col items-center gap-4 py-4 text-center sm:flex-row sm:text-left">
            <div className="flex-1">
              <p className="font-semibold text-ink">No products found</p>
              <p className="mt-1 text-sm text-ink-soft">
                Load the pre-built Indian product catalogue (~500 products across 12 categories) to get started instantly.
              </p>
            </div>
            <Button onClick={handleSeed} disabled={seeding}>
              <RefreshCw className={`h-4 w-4 ${seeding ? "animate-spin" : ""}`} />
              {seeding ? "Loading catalogue…" : "Load Indian Catalogue"}
            </Button>
          </div>
        </Panel>
      )}

      {seedResult && (
        <div className="rounded-lg border border-verified/40 bg-verified-soft px-4 py-3 text-sm text-verified">
          ✅ Catalogue loaded — <strong>{seedResult.inserted}</strong> products added
          {seedResult.skipped > 0 && `, ${seedResult.skipped} already existed`}.
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <form onSubmit={handleSearch} className="flex flex-1 gap-2">
          <SearchInput
            placeholder="Search by name, brand or barcode…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="max-w-sm"
          />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <div className="flex items-center gap-2">
          {products.length > 0 && (
            <Button variant="secondary" onClick={handleSeed} disabled={seeding} title="Re-seed to add any newly added catalogue items">
              <RefreshCw className={`h-4 w-4 ${seeding ? "animate-spin" : ""}`} />
              {seeding ? "Seeding…" : "Sync Catalogue"}
            </Button>
          )}
          <Button onClick={() => setShowForm((s) => !s)}>
            {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {showForm ? "Cancel" : "New product"}
          </Button>
        </div>
      </div>

      {showForm && (
        <div className="space-y-6">
          <Panel>
            <SectionHeading subtitle="Enter an Indian EAN-13 barcode (e.g. 8904004400731 for Haldiram's) to auto-fetch metadata from Open Food Facts.">
              Auto-Register Product via Barcode
            </SectionHeading>
            <BarcodeLookupForm
              onCreated={(p) => {
                setProducts((prev) => [p, ...prev]);
                setShowForm(false);
              }}
            />
          </Panel>

          <Panel>
            <SectionHeading subtitle="Products need a name at minimum — everything else can be filled in later.">
              Manual New Product Entry
            </SectionHeading>
            <NewProductForm
              onCreated={(p) => {
                setProducts((prev) => [p, ...prev]);
                setShowForm(false);
              }}
            />
          </Panel>
        </div>
      )}

      <Panel>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <SectionHeading>
            Products
            {filtered.length > 0 && (
              <span className="ml-2 text-sm font-normal text-ink-soft">({filtered.length})</span>
            )}
          </SectionHeading>
          {categories.length > 2 && (
            <div className="flex items-center gap-2">
              <label htmlFor="category-filter" className="text-sm text-ink-soft shrink-0">
                Filter by category:
              </label>
              <select
                id="category-filter"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-lg border border-rule bg-surface px-3 py-1.5 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-action"
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <ErrorNote>{error}</ErrorNote>
        {loading ? (
          <EmptyState>Loading…</EmptyState>
        ) : filtered.length === 0 ? (
          <EmptyState icon={<Boxes className="h-5 w-5" />}>
            {q || categoryFilter !== "All"
              ? `No products match your search${categoryFilter !== "All" ? ` in "${categoryFilter}"` : ""}.`
              : "No products yet — add one above to start a scan against it."}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table w-full text-left text-sm">
              <thead>
                <tr className="border-b border-rule">
                  <th className="py-2.5 font-medium">Name</th>
                  <th className="py-2.5 font-medium">Brand</th>
                  <th className="py-2.5 font-medium">Category</th>
                  <th className="py-2.5 font-medium">Manufacturer</th>
                  <th className="py-2.5 font-medium">Imported</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id} className="border-b border-rule/60 last:border-0">
                    <td className="py-3">
                      <Link to={`/products/${p.id}`} className="font-medium text-action hover:underline">
                        {p.name}
                      </Link>
                    </td>
                    <td className="py-3 text-ink-soft">{p.brand ?? "—"}</td>
                    <td className="py-3">
                      {p.category ? (
                        <span className="inline-flex items-center rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-ink-soft ring-1 ring-rule">
                          {p.category}
                        </span>
                      ) : (
                        <span className="text-ink-soft">—</span>
                      )}
                    </td>
                    <td className="py-3 text-ink-soft">{p.manufacturer_name ?? "—"}</td>
                    <td className="py-3">
                      {p.is_imported ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-caution-soft px-2 py-0.5 text-xs font-semibold text-caution">
                          Imported
                        </span>
                      ) : (
                        <span className="text-ink-soft">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
        <TextInput required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Refined Sunflower Oil 1L" />
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
      <label className="flex items-center gap-2 rounded-lg border border-rule bg-paper px-3.5 py-2.5 text-sm text-ink-soft sm:col-span-2">
        <input
          type="checkbox"
          checked={isImported}
          onChange={(e) => setIsImported(e.target.checked)}
          className="h-4 w-4 rounded border-rule text-action focus:ring-action"
        />
        Imported product (adds the country-of-origin declaration requirement)
      </label>
      <div className="sm:col-span-2">
        <ErrorNote>{error}</ErrorNote>
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          <PlusCircle className="h-4 w-4" />
          {submitting ? "Saving…" : "Save product"}
        </Button>
      </div>
    </form>
  );
}

function BarcodeLookupForm({ onCreated }: { onCreated: (p: Product) => void }) {
  const [barcode, setBarcode] = useState("");
  const [error, setError] = useState("");
  const [lookingUp, setLookingUp] = useState(false);

  async function handleLookup(e: FormEvent) {
    e.preventDefault();
    if (!barcode.trim()) return;
    setError("");
    setLookingUp(true);
    try {
      const product = await api.lookupProductByBarcode(barcode.trim());
      onCreated(product);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lookup failed.");
    } finally {
      setLookingUp(false);
    }
  }

  return (
    <form onSubmit={handleLookup} className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex-1">
        <Field label="EAN-13 / GTIN Barcode">
          <TextInput
            required
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            placeholder="e.g. 8904004400731 (Haldiram's Aloo Bhujia)"
          />
        </Field>
      </div>
      <Button type="submit" disabled={lookingUp || !barcode.trim()}>
        {lookingUp ? "Searching Open Food Facts…" : "Auto-Fetch & Add Product"}
      </Button>
      {error && <span className="text-xs text-seal font-medium">{error}</span>}
    </form>
  );
}
