import type {
  ApiErrorBody,
  Product,
  ProductInput,
  RuleVersion,
  Scan,
  ScanStatus,
  User,
  Violation,
  ViolationSeverity,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "lmc_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (!body.detail) return res.statusText;
    if (typeof body.detail === "string") return body.detail;
    return body.detail.map((d) => d.msg).join(", ");
  } catch {
    return res.statusText;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  { skipAuth = false }: { skipAuth?: boolean } = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormLike = init.body instanceof FormData || init.body instanceof URLSearchParams;
  if (!isFormLike && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (!skipAuth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const detail = await parseErrorDetail(res);
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

function qs(params: Record<string, string | boolean | undefined | null>): string {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (usable.length === 0) return "";
  const search = new URLSearchParams(usable.map(([k, v]) => [k, String(v)]));
  return `?${search.toString()}`;
}

// ---- Auth ----

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const data = await request<{ access_token: string }>(
    "/auth/login",
    { method: "POST", body },
    { skipAuth: true }
  );
  return data.access_token;
}

export function fetchMe(): Promise<User> {
  return request<User>("/auth/me");
}

// ---- Products ----

export function listProducts(q?: string): Promise<Product[]> {
  return request<Product[]>(`/products${qs({ q })}`);
}

export function getProduct(id: string): Promise<Product> {
  return request<Product>(`/products/${id}`);
}

export function lookupProductByBarcode(barcode: string): Promise<Product> {
  return request<Product>(`/products/lookup?barcode=${encodeURIComponent(barcode)}`);
}

export function createProduct(input: ProductInput): Promise<Product> {
  return request<Product>("/products", { method: "POST", body: JSON.stringify(input) });
}

export function updateProduct(id: string, input: Partial<ProductInput>): Promise<Product> {
  return request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteProduct(id: string): Promise<void> {
  return request<void>(`/products/${id}`, { method: "DELETE" });
}

export function seedProducts(): Promise<{ inserted: number; skipped: number; total_seed_entries: number }> {
  return request(`/products/seed`, { method: "POST" });
}


// ---- Scans ----

export function listScans(filters: {
  status?: ScanStatus;
  product_id?: string;
  created_by_id?: string;
}): Promise<Scan[]> {
  return request<Scan[]>(`/scans${qs(filters)}`);
}

export function getScan(id: string): Promise<Scan> {
  return request<Scan>(`/scans/${id}`);
}

export function createScan(input: { product_id: string; calibration_px_per_mm?: number }): Promise<Scan> {
  return request<Scan>("/scans", { method: "POST", body: JSON.stringify(input) });
}

export function updateScan(
  id: string,
  input: { status?: ScanStatus; calibration_px_per_mm?: number }
): Promise<Scan> {
  return request<Scan>(`/scans/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function evaluateScan(id: string): Promise<Scan> {
  return request<Scan>(`/scans/${id}/evaluate`, { method: "POST" });
}

export function uploadScanImage(id: string, file: File): Promise<Scan> {
  const form = new FormData();
  form.append("file", file);
  return request<Scan>(`/scans/${id}/image`, { method: "POST", body: form });
}

export function reprocessScan(id: string): Promise<Scan> {
  return request<Scan>(`/scans/${id}/reprocess`, { method: "POST" });
}

export function deleteScan(id: string): Promise<void> {
  return request<void>(`/scans/${id}`, { method: "DELETE" });
}

export function scanImageUrl(imagePath: string): string {
  return `${API_URL}/storage/${imagePath}`;
}

/**
 * Reports (Step 7) are downloaded rather than fetched as JSON, and need
 * the auth header attached same as every other request — a plain <a
 * href> can't carry that, so this fetches the file as a blob and drives
 * the browser's save dialog manually. Pulls the real filename off
 * Content-Disposition (set by routers/reports.py's FileResponse) rather
 * than guessing one, so it matches exactly what the backend generated.
 */
export async function downloadScanReport(id: string, format: "pdf" | "docx"): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}/scans/${id}/report?format=${format}`, { headers });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match ? match[1] : `compliance-report-${id.slice(0, 8)}.${format}`;

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// ---- Violations ----

export function listViolations(filters: {
  scan_id?: string;
  rule_id?: string;
  severity?: ViolationSeverity;
  is_resolved?: boolean;
}): Promise<Violation[]> {
  return request<Violation[]>(`/violations${qs(filters)}`);
}

export function updateViolation(
  id: string,
  input: { is_resolved?: boolean; resolution_note?: string; severity?: ViolationSeverity }
): Promise<Violation> {
  return request<Violation>(`/violations/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

// ---- Rule versions ----

export function listRuleVersions(): Promise<RuleVersion[]> {
  return request<RuleVersion[]>("/rule-versions");
}

export function getActiveRuleVersion(): Promise<RuleVersion> {
  return request<RuleVersion>("/rule-versions/active");
}

export function syncRuleVersionFromFile(): Promise<RuleVersion> {
  return request<RuleVersion>("/rule-versions/sync-from-file", { method: "POST" });
}

// ---- Users ----

export function listUsers(): Promise<User[]> {
  return request<User[]>("/users");
}

export function updateUser(
  id: string,
  input: { full_name?: string; role?: string; is_active?: boolean }
): Promise<User> {
  return request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function registerUser(input: {
  email: string;
  full_name: string;
  password: string;
  role: string;
}): Promise<User> {
  return request<User>("/auth/register", { method: "POST", body: JSON.stringify(input) });
}
