export type SystemInfo = { name: string; version: string; stage: "foundation" };

export async function fetchSystem(): Promise<SystemInfo> {
  const response = await fetch("/api/v1/system", {
    signal: AbortSignal.timeout(5000),
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("API недоступен");
  const body: unknown = await response.json();
  if (
    typeof body !== "object" ||
    body === null ||
    !("name" in body) ||
    typeof body.name !== "string" ||
    !("version" in body) ||
    typeof body.version !== "string" ||
    !("stage" in body) ||
    body.stage !== "foundation"
  ) {
    throw new Error("Неожиданный ответ API");
  }
  return { name: body.name, version: body.version, stage: body.stage };
}
