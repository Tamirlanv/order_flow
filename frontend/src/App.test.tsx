import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

function renderApp() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <App />
    </QueryClientProvider>,
  );
}

const healthy = () =>
  new Response(
    JSON.stringify({
      name: "OrderFlow",
      version: "0.1.0",
      stage: "foundation",
    }),
  );

describe("workspace", () => {
  it("shows the live API version and labels future features", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(healthy()));
    renderApp();
    expect(await screen.findByText("API подключён")).toBeInTheDocument();
    expect(
      screen.getByText("OrderFlow API · версия 0.1.0"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Запланировано")).toHaveLength(3);
  });

  it("shows loading without claiming a connection", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    renderApp();
    expect(screen.getByText("Проверяем подключение")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Проверяем…" })).toBeDisabled();
  });

  it("can recover from an unavailable API using the retry button", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(healthy());
    vi.stubGlobal("fetch", fetch);
    renderApp();
    expect(await screen.findByText("API не подключён")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить снова" }),
    );
    expect(await screen.findByText("API подключён")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not render malformed API responses as a success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response('{"name":"OrderFlow"}')),
    );
    renderApp();
    expect(await screen.findByText("API не подключён")).toBeInTheDocument();
  });

  it("opens the roadmap and returns to overview", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(healthy()));
    renderApp();
    await screen.findByText("API подключён");
    await userEvent.click(
      screen.getByRole("button", { name: "Посмотреть план" }),
    );
    expect(
      screen.getByRole("heading", { name: "Команда и доступ" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Обзор" }));
    expect(
      screen.getByRole("heading", { name: /Заказы под контролем/ }),
    ).toBeInTheDocument();
  });
});
