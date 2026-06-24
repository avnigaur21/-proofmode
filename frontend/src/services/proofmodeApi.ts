import type { ProofRun, ProofRunCreate } from "../types/runs";

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
