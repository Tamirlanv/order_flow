import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Box,
  Check,
  ChevronRight,
  Circle,
  Code2,
  Layers3,
  LayoutDashboard,
  Map,
  Package,
  Radio,
  RefreshCw,
  ShieldCheck,
  Truck,
} from "lucide-react";
import { fetchSystem } from "./api";

const roadmap = [
  {
    title: "Основа платформы",
    caption: "API, интерфейс и проверки",
    status: "В работе",
    icon: Layers3,
  },
  {
    title: "Команда и доступ",
    caption: "Аккаунты, магазины и роли",
    status: "Далее",
    icon: ShieldCheck,
  },
  {
    title: "Каталог и заказы",
    caption: "Товары и безопасный резерв",
    status: "Запланировано",
    icon: Package,
  },
  {
    title: "Оплата и доставка",
    caption: "События, повторы и уведомления",
    status: "Запланировано",
    icon: Truck,
  },
];

export default function App() {
  const [view, setView] = useState<"overview" | "roadmap">("overview");
  const api = useQuery({ queryKey: ["system"], queryFn: fetchSystem });
  const status = api.isFetching
    ? "Проверяем подключение"
    : api.isError
      ? "API не подключён"
      : "API подключён";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        К содержимому
      </a>
      <aside className="sidebar" aria-label="Боковая панель">
        <a href="/" className="brand" aria-label="OrderFlow — главная">
          <span className="brand-icon">
            <Box size={23} strokeWidth={1.8} />
          </span>
          Order<span>Flow</span>
        </a>
        <div className="workspace">
          <span className="workspace-avatar">O</span>
          <div>
            Рабочее пространство<small>Версия для разработки</small>
          </div>
        </div>
        <p className="nav-caption">ПЛАТФОРМА</p>
        <nav aria-label="Навигация">
          <button
            className={`nav-item ${view === "overview" ? "active" : ""}`}
            onClick={() => setView("overview")}
            aria-current={view === "overview" ? "page" : undefined}
          >
            <LayoutDashboard size={18} /> Обзор <ChevronRight size={15} />
          </button>
          <button
            className={`nav-item ${view === "roadmap" ? "active" : ""}`}
            onClick={() => setView("roadmap")}
            aria-current={view === "roadmap" ? "page" : undefined}
          >
            <Map size={18} /> План развития <ChevronRight size={15} />
          </button>
          <a className="nav-item" href="/docs" target="_blank" rel="noreferrer">
            <Code2 size={18} /> Документация API <ArrowUpRight size={15} />
          </a>
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" /> Создаём основу
          <p>Надёжные заказы начинаются с правильной архитектуры.</p>
        </div>
        <div className="sidebar-footer">
          <span>ORDERFLOW</span>
          <span>v{api.data?.version ?? "0.1.0"}</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div>
            Платформа <ChevronRight size={13} />
            <strong>{view === "overview" ? "Обзор" : "План развития"}</strong>
          </div>
          <span className="build-badge">
            Ранняя версия <span>01</span>
          </span>
        </header>
        <main id="main" tabIndex={-1}>
          {view === "overview" ? (
            <>
              <section className="hero" aria-labelledby="hero-title">
                <div className="eyebrow">
                  <span className="small-dot" /> ОДНО ПРОСТРАНСТВО. ВЕСЬ
                  ПРОЦЕСС.
                </div>
                <h1 id="hero-title">
                  Заказы под контролем.
                  <br />
                  <span>От витрины до двери.</span>
                </h1>
                <p className="hero-description">
                  Товары, остатки и доставка в одном месте.
                  <br className="desktop-break" /> Строим систему, на которую
                  можно положиться.
                </p>
                <div className="hero-actions">
                  <button
                    className="primary-button"
                    onClick={() => setView("roadmap")}
                  >
                    Посмотреть план <ArrowRight size={17} />
                  </button>
                  <a className="text-button" href="#connection">
                    Проверить подключение <ArrowDown size={15} />
                  </a>
                </div>
                <div className="orbital-art" aria-hidden="true">
                  <div className="orbit orbit-one" />
                  <div className="orbit orbit-two" />
                  <div className="orbit-core">
                    <Box size={55} strokeWidth={1.1} />
                  </div>
                  <span className="orbit-dot" />
                  <span className="orbit-label">CONNECTED COMMERCE</span>
                </div>
              </section>

              <div className="section-heading">
                <div>
                  <span className="eyebrow">ОТ ЗАКАЗА К РЕЗУЛЬТАТУ</span>
                  <h2>Каждый шаг на своём месте</h2>
                </div>
                <span className="quiet-tag">Возможности в разработке</span>
              </div>
              <section
                className="flow-grid"
                aria-label="Планируемые возможности"
              >
                {[
                  {
                    icon: Package,
                    number: "01",
                    title: "Заказы",
                    text: "С витрины и партнёрского API — в единую очередь.",
                  },
                  {
                    icon: Layers3,
                    number: "02",
                    title: "Остатки",
                    text: "Резервирование товара без двойной продажи.",
                  },
                  {
                    icon: Truck,
                    number: "03",
                    title: "Доставка",
                    text: "Обработка событий и контроль каждого отправления.",
                  },
                ].map(({ icon: Icon, number, title, text }) => (
                  <article className="flow-card" key={title}>
                    <div className="card-top">
                      <Icon size={24} strokeWidth={1.5} />
                      <span>{number}</span>
                    </div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                    <span className="planned-label">
                      <Circle size={8} /> Запланировано
                    </span>
                  </article>
                ))}
              </section>

              <section
                className="connection-panel"
                id="connection"
                aria-labelledby="connection-title"
              >
                <div className="connection-copy">
                  <span className="eyebrow">ТЕКУЩИЙ ЭТАП · M01</span>
                  <h2 id="connection-title">Основа уже обретает форму</h2>
                  <p>
                    Интерфейс связывается с сервером. Работа с магазинами и
                    заказами появится на следующих этапах.
                  </p>
                  <div className="foundation-points">
                    <span>
                      <Check size={15} /> Структура приложения
                    </span>
                    <span>
                      <Check size={15} /> Контракт API
                    </span>
                    <span>
                      <Circle size={11} /> Проверка инфраструктуры впереди
                    </span>
                  </div>
                </div>
                <div className="status-card">
                  <div className="status-card-heading">
                    <Radio size={19} />
                    <span>Подключение к серверу</span>
                  </div>
                  <div className="connection-status" role="status">
                    <span
                      className={`status-indicator ${api.isError ? "offline" : ""}`}
                    />
                    {status}
                  </div>
                  <p>
                    {api.isError
                      ? "Запустите backend локально и повторите проверку."
                      : api.isFetching
                        ? "Запрашиваем состояние приложения…"
                        : `OrderFlow API · версия ${api.data?.version}`}
                  </p>
                  <button
                    className="check-button"
                    disabled={api.isFetching}
                    onClick={() => {
                      void api.refetch();
                    }}
                  >
                    <RefreshCw
                      size={15}
                      className={api.isFetching ? "spin" : ""}
                    />
                    {api.isFetching ? "Проверяем…" : "Проверить снова"}
                  </button>
                  <small>
                    Подключение к API не означает готовность базы данных и
                    очередей.
                  </small>
                </div>
              </section>
            </>
          ) : (
            <section className="roadmap-page">
              <span className="eyebrow">ПРОЗРАЧНЫЙ ПУТЬ К MVP</span>
              <h1>
                Шаг за шагом.
                <br />
                <span>Функция за функцией.</span>
              </h1>
              <p className="hero-description">
                Каждый этап начинается со спецификации
                <br />и заканчивается проверкой поведения.
              </p>
              <div className="roadmap-list">
                {roadmap.map(
                  (
                    { title, caption, status: phaseStatus, icon: Icon },
                    index,
                  ) => (
                    <article className="roadmap-row" key={title}>
                      <span className="step-number">0{index + 1}</span>
                      <Icon size={24} />
                      <div>
                        <h2>{title}</h2>
                        <p>{caption}</p>
                      </div>
                      <span className="quiet-tag">{phaseStatus}</span>
                    </article>
                  ),
                )}
              </div>
              <p className="roadmap-note">
                M01 пока не завершён: запуск полного окружения и проверки
                инфраструктуры отложены. Заказы, авторизация и платежи ещё не
                реализованы.
              </p>
            </section>
          )}
          <footer className="page-footer">
            <span>
              OrderFlow <span className="footer-dot">/</span> Больше порядка.
              Меньше рутины.
            </span>
            <span>Сделано с вниманием к деталям</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
