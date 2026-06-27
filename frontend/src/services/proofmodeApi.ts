import type { ApprovalCreate, ProofRun, ProofRunCreate } from "../types/runs";
import type { SettingsStatus } from "../types/settings";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function artifactUrl(path?: string | null): string | null {
  if (!path) {
    return null;
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}

export async function createRun(payload: ProofRunCreate): Promise<ProofRun> {
  const response = await fetch(`${API_BASE_URL}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Unable to create ProofMode run");
  }

  return response.json();
}

export async function listRuns(): Promise<ProofRun[]> {
  const response = await fetch(`${API_BASE_URL}/runs`);

  if (!response.ok) {
    throw new Error("Unable to load ProofMode runs");
  }

  return response.json();
}

export async function getSettingsStatus(): Promise<SettingsStatus> {
  const response = await fetch(`${API_BASE_URL}/settings/status`);

  if (!response.ok) {
    throw new Error("Unable to load ProofMode settings status");
  }

  return response.json();
}

export async function seedDemoRuns(): Promise<ProofRun[]> {
  const response = await fetch(`${API_BASE_URL}/demo/seed`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Unable to seed demo runs");
  }

  return response.json();
}

export async function recordApproval(runId: string, payload: ApprovalCreate): Promise<ProofRun> {
  const response = await fetch(`${API_BASE_URL}/runs/${runId}/approval`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Unable to record approval decision");
  }

  return response.json();
}

export async function loadTextArtifact(path?: string | null): Promise<string> {
  const url = artifactUrl(path);
  if (!url) {
    throw new Error("Artifact URL is missing");
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error("Unable to load artifact");
  }

  return response.text();
}
