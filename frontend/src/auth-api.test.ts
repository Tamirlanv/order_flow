import { describe, expect, it, vi } from "vitest";
import { authAction } from "./auth-api";

describe("CSRF fail closed", () => {
  it.each([
    "register",
    "login",
    "verification/request",
    "verification/confirm",
    "logout",
  ])("does not submit %s when CSRF retrieval fails", async (action) => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }));
    vi.stubGlobal("fetch", fetch);
    await expect(authAction(action, {})).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/csrf");
  });
});
