export interface ParsedFields {
  region: "EU" | "CN" | "Global" | "EU+CN" | null;
  data_types: ("Personal" | "Behavioral" | "Biometric" | "Financial")[] | null;
  cross_border: boolean | null;
  third_party_model: boolean | null;
  aigc_output: boolean | null;
  data_volume_level: "Small" | "Medium" | "Large" | null;
}

export interface EvidenceChunk {
  regulation: string;
  article_id?: string;
  article?: string;
  chapter?: string | null;
  text_excerpt?: string;
  text?: string;
  summary?: string | null;
  relevance_score?: number;
  rerank_score?: number | null;
}

export interface RemediationAction {
  role: string;
  action?: string;       // backend returns single string
  actions?: string[];    // future/aggregated format
  priority?: string;
  regulation_ref?: string;
}

export interface AuditReport {
  report_id: string;
  summary: string;
  risk_level: "Low" | "Medium" | "High" | "Critical";
  risk_overview: string;
  evidence_citations: EvidenceChunk[];
  uncertainties: string[];
  remediation_actions: RemediationAction[];
  disclaimer: string;
  created_at: string;
}

export interface ReportSummary {
  report_id: string;
  summary?: string;
  risk_overview?: string;
  risk_level: "Low" | "Medium" | "High" | "Critical";
  created_at: string;
}

export interface ProgressEvent {
  step: string;
  status: "running" | "completed" | "waiting" | "error";
  message: string;
  data?: {
    questions?: FollowUpQuestion[];
    report_id?: string;
    [key: string]: unknown;
  };
}

export interface FollowUpQuestion {
  field: string;
  question: string;
  options: string[];
}

export interface FeedbackPayload {
  section: string;
  rating: "helpful" | "unhelpful" | "needs_edit";
  comment?: string | null;
}
