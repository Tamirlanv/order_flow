import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, LogOut, Mail, ShieldCheck } from "lucide-react";
import { authAction, fetchMe } from "./auth-api";
import "./auth.css";

export default function AuthPanel() {
  const [mode, setMode] = useState<"login" | "register" | "resend">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(() =>
    new URLSearchParams(window.location.hash.slice(1)).get("verify"),
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, retry: false });

  useEffect(() => {
    if (token)
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
  }, [token]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Запрос не выполнен",
      );
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await authAction(
        mode === "resend" ? "verification/request" : mode,
        mode === "resend" ? { email } : { email, password },
      );
      setPassword("");
      if (mode === "login")
        await queryClient.invalidateQueries({ queryKey: ["me"] });
      else
        setMessage(
          "Если адрес подходит для регистрации, мы отправили инструкции. Проверьте почту; если письмо не пришло, повторите отправку.",
        );
    });
  }

  return (
    <section className="account-page" aria-labelledby="account-title">
      <div className="eyebrow">
        <ShieldCheck size={16} /> ВАШЕ РАБОЧЕЕ ПРОСТРАНСТВО
      </div>
      <h1 id="account-title">
        Начнём с <span>знакомства.</span>
      </h1>
      <p className="account-intro">
        Один аккаунт для ваших магазинов и команды.
      </p>
      <div className="account-grid">
        <div className="account-card">
          {token ? (
            <>
              <span className="account-icon">
                <Mail size={24} />
              </span>
              <h2>Подтверждение email</h2>
              <p>
                Подтвердите адрес, чтобы войти в OrderFlow. Ссылка действует 24
                часа и используется один раз.
              </p>
              <button
                className="primary-button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await authAction("verification/confirm", { token });
                    setToken(null);
                    setMessage("Email подтверждён. Теперь можно войти.");
                  })
                }
              >
                {busy ? "Проверяем…" : "Подтвердить email"}
                <Check size={17} />
              </button>
              <button
                className="account-link"
                disabled={busy}
                onClick={() => {
                  setToken(null);
                  setMode("resend");
                  setError("");
                }}
              >
                Запросить новую ссылку
              </button>
            </>
          ) : me.isPending ? (
            <p role="status">Проверяем сессию…</p>
          ) : me.isError ? (
            <>
              <p role="alert">
                Не удалось проверить сессию. Убедитесь, что API доступен.
              </p>
              <button
                className="primary-button"
                onClick={() => void me.refetch()}
              >
                Повторить
              </button>
            </>
          ) : me.data ? (
            <>
              <span className="account-icon">
                <ShieldCheck size={24} />
              </span>
              <h2>Вы в OrderFlow</h2>
              <p className="account-email">{me.data.email}</p>
              <p>
                Аккаунт подтверждён. Управление магазинами появится на следующем
                этапе.
              </p>
              <button
                className="primary-button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await authAction("logout");
                    queryClient.setQueryData(["me"], null);
                    setMessage("Вы вышли из аккаунта");
                  })
                }
              >
                Выйти
                <LogOut size={17} />
              </button>
            </>
          ) : (
            <>
              <div className="account-tabs">
                <button
                  className={mode === "login" ? "selected" : ""}
                  onClick={() => {
                    setMode("login");
                    setMessage("");
                    setError("");
                  }}
                >
                  Вход
                </button>
                <button
                  className={mode === "register" ? "selected" : ""}
                  onClick={() => {
                    setMode("register");
                    setMessage("");
                    setError("");
                  }}
                >
                  Регистрация
                </button>
              </div>
              <h2>
                {mode === "login"
                  ? "Рады видеть вас"
                  : mode === "register"
                    ? "Создайте аккаунт"
                    : "Новое письмо"}
              </h2>
              <form onSubmit={submit}>
                <label>
                  Email
                  <input
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={320}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                {mode !== "resend" && (
                  <label>
                    Пароль
                    <input
                      type="password"
                      autoComplete={
                        mode === "login" ? "current-password" : "new-password"
                      }
                      required
                      minLength={12}
                      maxLength={128}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      aria-describedby="password-hint"
                    />
                  </label>
                )}
                {mode !== "resend" && (
                  <p id="password-hint" className="field-hint">
                    От 12 до 128 символов. Пробелы и Unicode разрешены.
                  </p>
                )}
                <button
                  className="primary-button"
                  disabled={busy}
                  type="submit"
                >
                  {busy
                    ? "Подождите…"
                    : mode === "login"
                      ? "Войти"
                      : mode === "register"
                        ? "Создать аккаунт"
                        : "Отправить письмо"}
                  <ArrowRight size={17} />
                </button>
              </form>
              <button
                className="account-link"
                disabled={busy}
                onClick={() => {
                  setMode("resend");
                  setError("");
                  setMessage("");
                }}
              >
                Не пришло письмо подтверждения?
              </button>
            </>
          )}
          {error && (
            <p className="account-message error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="account-message" role="status">
              {message}
            </p>
          )}
        </div>
        <aside className="account-aside">
          <span className="small-dot" /> ПРОСТОЙ СТАРТ
          <h2>
            Сначала команда.
            <br />
            Потом — большие дела.
          </h2>
          <ol>
            <li>
              <span>01</span>
              <div>
                Создайте аккаунт<small>Ваш email и надёжный пароль</small>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                Подтвердите адрес<small>Одна ссылка в вашей почте</small>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                Войдите в пространство
                <small>Доступ к аккаунту с любого устройства</small>
              </div>
            </li>
          </ol>
        </aside>
      </div>
    </section>
  );
}
