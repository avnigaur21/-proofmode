import type { ProofRun } from "../types/runs";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function createRun(claim: string): Promise<ProofRun> {
  const response = await fetch(`${API_BASE_URL}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ claim }),
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

