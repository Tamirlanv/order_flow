export type User = { id: string; email: string };

async function decode(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const body: unknown = await response.json();
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? body.detail
        : null;
    throw new Error(
      typeof detail === "string"
        ? detail
        : "Проверьте введённые данные и повторите запрос",
    );
  }
  return body;
}

export async function fetchMe(): Promise<User | null> {
  const response = await fetch("/api/v1/auth/me", {
    signal: AbortSignal.timeout(10000),
  });
  if (response.status === 401) return null;
  const body = await decode(response);
  if (
    typeof body !== "object" ||
    body === null ||
    !("id" in body) ||
    !("email" in body) ||
    typeof body.id !== "string" ||
    typeof body.email !== "string"
  ) {
    throw new Error("Не удалось прочитать данные аккаунта");
  }
  return { id: body.id, email: body.email };
}

export async function authAction(path: string, data?: object): Promise<void> {
  const csrfResponse = await fetch("/api/v1/auth/csrf", {
    signal: AbortSignal.timeout(10000),
  });
  const csrf = await decode(csrfResponse);
  if (
    typeof csrf !== "object" ||
    csrf === null ||
    !("csrf_token" in csrf) ||
    typeof csrf.csrf_token !== "string"
  ) {
    throw new Error("Обновите страницу и повторите запрос");
  }
  await decode(
    await fetch(`/api/v1/auth/${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf.csrf_token,
      },
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(20000),
    }),
  );
}
