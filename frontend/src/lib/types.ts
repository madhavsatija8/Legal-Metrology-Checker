// Mirrors backend/app/schemas.py and models.py. Keep these in sync by
// hand for now — if the API grows a schema-export step later, generate
// this file instead of maintaining it manually.

export type UserRole = "inspector" | "supervisor" | "admin";

export type ScanStatus = "pending" | "processing" | "review" | "resolved" | "escalated";

export type ViolationSeverity = "minor" | "major" | "critical";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Product {
  id: string;
  name: string;
  brand?: string | null;
  category?: string | null;
  manufacturer_name?: string | null;
  is_imported: boolean;
  surface_treatment?: string | null;
  created_at: string;
}

export interface ProductInput {
  name: string;
  brand?: string;
  category?: string;
  manufacturer_name?: string;
  is_imported?: boolean;
  surface_treatment?: string;
}

export interface Violation {
  id: string;
  scan_id: string;
  rule_id: string;
  citation?: string | null;
  description: string;
  severity: ViolationSeverity;
  needs_review: boolean;
  is_resolved: boolean;
  resolution_note?: string | null;
  created_at: string;
}

// The OCR pipeline's per-field output shape is intentionally loose
// (backend/app/ocr/field_classifier.py) — every field is an object with
// at least `matched`, plus assorted keys depending on the field
// (value/amount/phone/email/source_line/pixel_height/...).
export interface ExtractedField {
  matched: boolean;
  source_line?: string | null;
  pixel_height?: number | null;
  [key: string]: unknown;
}

export interface ExtractedFields {
  raw_lines: string[];
  word_count: number;
  average_ocr_confidence: number;
  fields: Record<string, ExtractedField>;
  error?: string;
}

export interface ComplianceReviewItem {
  rule_id: string;
  category: string;
  note: string;
}

export interface ComplianceReview {
  exempt: boolean;
  exemption_reason?: string | null;
  review_items: ComplianceReviewItem[];
}

export interface Scan {
  id: string;
  product_id: string;
  created_by_id: string;
  status: ScanStatus;
  image_path?: string | null;
  extracted_fields?: ExtractedFields | null;
  calibration_px_per_mm?: number | null;
  compliance_review?: ComplianceReview | null;
  rule_version_id?: string | null;
  created_at: string;
  updated_at: string;
  violations: Violation[];
}

export interface RuleVersion {
  id: string;
  version_label: string;
  source_file_hash: string;
  is_active: boolean;
  activated_at: string;
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
}
