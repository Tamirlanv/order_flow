import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import AuthPanel from "./AuthPanel";

function renderPanel() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <AuthPanel />
    </QueryClientProvider>,
  );
}
const response = (body: object, status = 200) =>
  new Response(JSON.stringify(body), { status });
const guest = () => response({ detail: "Войдите в аккаунт" }, 401);
afterEach(() => window.history.replaceState(null, "", "/"));

describe("accounts", () => {
  it("registers with CSRF and shows email instructions without storing the password", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(guest())
      .mockResolvedValueOnce(response({ csrf_token: "bound-token" }))
      .mockResolvedValueOnce(response({ message: "instructions" }, 202));
    vi.stubGlobal("fetch", fetch);
    renderPanel();
    await userEvent.click(
      await screen.findByRole("button", { name: "Регистрация" }),
    );
    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("Пароль"), "long-password-test");
    await userEvent.click(
      screen.getByRole("button", { name: "Создать аккаунт" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Проверьте почту",
    );
    expect(screen.getByLabelText("Пароль")).toHaveValue("");
    expect(fetch.mock.calls[2][0]).toBe("/api/v1/auth/register");
    expect(fetch.mock.calls[2][1].headers["X-CSRF-Token"]).toBe("bound-token");
    expect(localStorage.length).toBe(0);
  });

  it("logs in, displays the account and logs out", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(guest())
      .mockResolvedValueOnce(response({ csrf_token: "anonymous" }))
      .mockResolvedValueOnce(
        response({
          user: { id: "1", email: "owner@example.com" },
          csrf_token: "session",
        }),
      )
      .mockResolvedValueOnce(response({ id: "1", email: "owner@example.com" }))
      .mockResolvedValueOnce(response({ csrf_token: "session" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    renderPanel();
    await userEvent.type(
      await screen.findByLabelText("Email"),
      "owner@example.com",
    );
    await userEvent.type(screen.getByLabelText("Пароль"), "long-password-test");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));
    expect(fetch.mock.calls[2][1].headers["X-CSRF-Token"]).toBe("anonymous");
    expect(await screen.findByText("Вы в OrderFlow")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Выйти" }));
    expect(await screen.findByText("Вы вышли из аккаунта")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(fetch.mock.calls[5][0]).toBe("/api/v1/auth/logout");
    expect(fetch.mock.calls[5][1].headers["X-CSRF-Token"]).toBe("session");
  });

  it("requires an explicit confirmation click and handles an expired link", async () => {
    window.history.replaceState(null, "", "/#verify=one-use-test-token");
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(guest())
      .mockResolvedValueOnce(response({ csrf_token: "anonymous" }))
      .mockResolvedValueOnce(
        response({ detail: "Ссылка недействительна или истекла" }, 400),
      );
    vi.stubGlobal("fetch", fetch);
    renderPanel();
    expect(window.location.hash).toBe("");
    expect(fetch).toHaveBeenCalledTimes(1);
    await userEvent.click(
      screen.getByRole("button", { name: "Подтвердить email" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ссылка недействительна или истекла",
    );
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({
      token: "one-use-test-token",
    });
    expect(fetch.mock.calls[2][1].headers["X-CSRF-Token"]).toBe("anonymous");
    await userEvent.click(
      screen.getByRole("button", { name: "Запросить новую ссылку" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Отправить письмо" }),
      ).toBeInTheDocument(),
    );
  });

  it("resends verification with CSRF", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(guest())
      .mockResolvedValueOnce(response({ csrf_token: "resend-token" }))
      .mockResolvedValueOnce(response({ message: "instructions" }, 202));
    vi.stubGlobal("fetch", fetch);
    renderPanel();
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Не пришло письмо подтверждения?",
      }),
    );
    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.click(
      screen.getByRole("button", { name: "Отправить письмо" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Проверьте почту",
    );
    expect(fetch.mock.calls[2][0]).toBe("/api/v1/auth/verification/request");
    expect(fetch.mock.calls[2][1].headers["X-CSRF-Token"]).toBe("resend-token");
  });
});
