import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";
import {
  Timer as TimerIcon,
  ListTodo,
  ChartNoAxesColumnIncreasing,
  Settings,
  Plus,
  Play,
  Pause,
  Square,
  SkipForward,
  ArrowUpRight,
  Search,
  Pencil,
  Trash2,
  X,
  Check,
  Coffee,
  Leaf,
  Bell,
  RotateCcw,
  ChevronRight,
  CircleHelp,
} from "lucide-react";
import type {
  Plan,
  Task,
  TaskInput,
  Timer,
  Preferences,
  Snapshot,
} from "./types";
import { clock, dateLabel, groupTasks, localDate } from "./lib";

type Page = "timer" | "tasks" | "progress" | "settings";
const defaults: Preferences = {
  focus_minutes: 25,
  break_minutes: 5,
  sessions: 4,
  final_break: false,
  notifications: false,
  sound: true,
};
const blank = (preferences = defaults): TaskInput => ({
  ...preferences,
  title: "",
  id: null,
  priority: 1,
  planned_date: localDate(),
});
const navigation = [
  { id: "timer", label: "Focus timer", icon: TimerIcon },
  { id: "tasks", label: "My tasks", icon: ListTodo },
  { id: "progress", label: "Progress", icon: ChartNoAxesColumnIncreasing },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

function PlanFields({
  value,
  onChange,
}: {
  value: Plan;
  onChange: (value: Plan) => void;
}) {
  return (
    <>
      <div className="plan-fields">
        {(["focus_minutes", "break_minutes", "sessions"] as const).map(
          (key, i) => (
            <label key={key}>
              {["Focus minutes", "Break minutes", "Sessions"][i]}
              <input
                type="number"
                required
                min={key === "break_minutes" ? 0 : 1}
                max={key === "sessions" ? 1000 : 1440}
                value={value[key]}
                onChange={(e) =>
                  onChange({
                    ...value,
                    [key]: e.target.value === "" ? "" : Number(e.target.value),
                  } as Plan)
                }
              />
            </label>
          ),
        )}
      </div>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={value.final_break}
          onChange={(e) =>
            onChange({ ...value, final_break: e.target.checked })
          }
        />{" "}
        Include a break after the final session
      </label>
    </>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("timer");
  const [data, setData] = useState<Snapshot | null>(null);
  const [timer, setTimer] = useState<Timer | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<TaskInput | null>(null);
  const [quick, setQuick] = useState<Plan>({ ...defaults, title: "Deep work" });
  const [prefs, setPrefs] = useState<Preferences>(defaults);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [deleted, setDeleted] = useState<number | null>(null);
  const [legacyPath, setLegacyPath] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const sound = useRef(defaults.sound);
  const loadedDefaults = useRef(false);
  const mounted = useRef(true);
  const dialog = useRef<HTMLDialogElement>(null);
  const desktop = isTauri();

  const reload = useCallback(async () => {
    const value = await invoke<Snapshot>("snapshot");
    if (!mounted.current) return;
    setData(value);
    setTimer(value.timer);
    sound.current = value.preferences.sound;
    if (!loadedDefaults.current) {
      setQuick({ ...value.preferences, title: "Deep work" });
      setPrefs(value.preferences);
      loadedDefaults.current = true;
    }
  }, []);
  const playSound = (finish = false) => {
    if (sound.current)
      void new Audio(finish ? "/finish_sound.mp3" : "/start_sound.mp3")
        .play()
        .catch(() => {});
  };
  const perform = async (
    command: string,
    args: Record<string, unknown> = {},
    message = "",
  ) => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await invoke(command, args);
      await reload();
      if (message) setNotice(message);
      return true;
    } catch (e) {
      setError(String(e));
      return false;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  useEffect(() => {
    mounted.current = true;
    if (!desktop)
      return () => {
        mounted.current = false;
      };
    let disposed = false;
    const cleanups: (() => void)[] = [];
    const subscribe = async <T,>(
      name: string,
      callback: (payload: T) => void,
    ) => {
      const stop = await listen<T>(name, (e) => {
        if (!disposed) callback(e.payload);
      });
      if (disposed) stop();
      else cleanups.push(stop);
    };
    void Promise.all([
      subscribe<Timer | null>("timer-tick", setTimer),
      subscribe("data-changed", () => {
        void reload().catch((e) => setError(String(e)));
      }),
      subscribe<string>("backend-error", setError),
      subscribe<string>("session-event", (message) => {
        setNotice(message);
        playSound(true);
      }),
    ])
      .then(() => {
        if (!disposed) return reload();
      })
      .catch((e) => {
        if (!disposed) setError(String(e));
      });
    const refresh = () => {
      void reload().catch((e) => setError(String(e)));
    };
    window.addEventListener("focus", refresh);
    // Refresh the local date and statistics across midnight, including while idle.
    const interval = window.setInterval(refresh, 60_000);
    return () => {
      disposed = true;
      mounted.current = false;
      cleanups.forEach((f) => f());
      window.removeEventListener("focus", refresh);
      window.clearInterval(interval);
    };
  }, [desktop, reload]);
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(id);
  }, [notice]);
  useEffect(() => {
    if (editor) dialog.current?.showModal();
    else dialog.current?.close();
  }, [editor !== null]);

  const today = data?.today ?? localDate();
  const todayStats = data?.stats.find((d) => d.date === today);
  const pending = data?.tasks.filter((t) => !t.completed) ?? [];
  const todayTasks = (data?.tasks ?? []).filter(
    (t) => t.planned_date === today,
  );
  const selectedTasks = groupTasks(data?.tasks ?? [], search, status, priority);
  const start = async (task?: Task) => {
    if (
      await perform("start_timer", {
        plan: task ?? quick,
        taskId: task?.id ?? null,
      })
    ) {
      setPage("timer");
      playSound();
    }
  };
  const action = (name: string) => {
    void perform("timer_action", { action: name });
  };
  const saveTask = async (event: FormEvent) => {
    event.preventDefault();
    if (
      editor &&
      (await perform("save_task", { input: editor }, "Task saved."))
    )
      setEditor(null);
  };
  const removeTask = async (task: Task) => {
    if (
      await perform(
        "delete_task",
        { id: task.id, restore: false },
        "Task deleted. You can undo below.",
      )
    )
      setDeleted(task.id);
  };
  const savePreferences = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      if (
        prefs.notifications &&
        !(await isPermissionGranted()) &&
        (await requestPermission()) !== "granted"
      ) {
        setError(
          "Notifications were not allowed. Enable them in your system settings.",
        );
        return;
      }
      if (
        await perform(
          "save_preferences",
          { preferences: prefs },
          "Preferences saved.",
        )
      ) {
        sound.current = prefs.sound;
        if (!timer) setQuick({ ...prefs, title: quick.title });
      }
    } catch (e) {
      setError(String(e));
    }
  };
  const taskRow = (task: Task) => (
    <div className={`task-row ${task.completed ? "done" : ""}`} key={task.id}>
      <button
        className={`check-task ${task.completed ? "checked" : ""}`}
        aria-label={
          task.completed ? `Reopen ${task.title}` : `Complete ${task.title}`
        }
        disabled={busy || !data}
        onClick={() =>
          void perform("complete_task", {
            id: task.id,
            completed: !task.completed,
          })
        }
      >
        {task.completed && <Check size={13} />}
      </button>
      <div className="task-content">
        <span className="task-name">{task.title}</span>
        <span className="task-meta">
          {task.focus_minutes}m focus <span>·</span> {task.break_minutes}m break{" "}
          <span>·</span> {task.completed_rounds}/{task.sessions} rounds
        </span>
      </div>
      <span className={`priority p${task.priority}`}>
        {["Low", "Normal", "High"][task.priority]}
      </span>
      <div className="task-actions">
        <button
          className="icon-button"
          title="Start task"
          aria-label={`Start ${task.title}`}
          disabled={busy || !!timer || task.completed}
          onClick={() => void start(task)}
        >
          <Play size={15} />
        </button>
        <button
          className="icon-button"
          title="Edit task"
          aria-label={`Edit ${task.title}`}
          disabled={busy}
          onClick={() => setEditor({ ...task })}
        >
          <Pencil size={15} />
        </button>
        <button
          className="icon-button delete"
          title="Delete task"
          aria-label={`Delete ${task.title}`}
          disabled={busy}
          onClick={() => void removeTask(task)}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("timer");
          }}
        >
          <img src="/focusnest-icon.png" alt="" />
          <span>
            FocusNest<span className="brand-caption">MAKE ROOM FOR FOCUS</span>
          </span>
        </a>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => setPage(item.id)}
            >
              <item.icon size={19} />
              <span>{item.label}</span>
              {item.id === "tasks" && (
                <span className="count">{pending.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="quiet-note">
            <Leaf size={21} />
            <p>
              One thing at a time.
              <br />
              <span>Good work starts here.</span>
            </p>
          </div>
          <div className="version">
            <span className="status-dot" /> Local & private <span>v0.3.0</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            <span className="muted">Workspace</span>
            <ChevronRight size={14} />
            {navigation.find((n) => n.id === page)?.label}
          </span>
          <span className="topbar-date">
            {new Date(`${today}T12:00:00`).toLocaleDateString(undefined, {
              weekday: "short",
              month: "short",
              day: "numeric",
            })}
          </span>
        </header>
        <div className="workspace">
          {!desktop && (
            <div className="banner">
              <CircleHelp size={18} />
              <span>
                This is the interface preview. Run <code>npm run desktop</code>{" "}
                to use the Rust timer and SQLite database.
              </span>
            </div>
          )}
          {desktop && !data && !error && (
            <div className="banner" role="status">
              Opening your workspace…
            </div>
          )}
          {error && (
            <div className="banner error" role="alert">
              <span>{error}</span>
              {!data && desktop && (
                <button
                  onClick={() =>
                    void reload().catch((e) => setError(String(e)))
                  }
                >
                  Retry
                </button>
              )}
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="banner success" role="status">
              <Check size={17} />
              <span>{notice}</span>
              <button
                className="icon-button"
                aria-label="Dismiss notice"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {page === "timer"
                  ? "A LITTLE FOCUS, A LITTLE PROGRESS"
                  : "YOUR PERSONAL WORKSPACE"}
              </span>
              <h1>
                {
                  {
                    timer: "Find your flow.",
                    tasks: "Make space for what matters.",
                    progress: "Small steps. Real progress.",
                    settings: "Make it yours.",
                  }[page]
                }
              </h1>
              <p>
                {
                  {
                    timer: "Set an intention. Settle in. Let the rest wait.",
                    tasks:
                      "A clear plan for today, and a little room for tomorrow.",
                    progress: "An honest picture of the time you put in.",
                    settings:
                      "A few thoughtful defaults for your daily rhythm.",
                  }[page]
                }
              </p>
            </div>
            {page === "tasks" && (
              <button
                className="primary"
                disabled={!data || busy}
                onClick={() => setEditor(blank(data?.preferences))}
              >
                <Plus size={17} />
                New task
              </button>
            )}
          </div>

          {page === "timer" && (
            <>
              <div className="focus-layout">
                <section className="card timer-card">
                  <div className="card-top">
                    <span className="pill">
                      <span
                        className={`status-dot ${timer && !timer.paused ? "running" : ""}`}
                      />
                      {timer
                        ? timer.paused
                          ? "PAUSED"
                          : timer.phase === "break"
                            ? "REST & RECHARGE"
                            : "FOCUS IN PROGRESS"
                        : "READY WHEN YOU ARE"}
                    </span>
                    <span className="subtle">
                      {timer
                        ? `${timer.session_index} of ${timer.sessions} rounds`
                        : `${quick.sessions} rounds planned`}
                    </span>
                  </div>
                  <div
                    className="timer-ring"
                    style={
                      {
                        "--progress": `${timer ? Math.min(100, Math.max(0, 1 - timer.remaining / ((timer.phase === "focus" ? timer.focus_minutes : timer.break_minutes) * 60 || 1)) * 100) : 0}%`,
                      } as React.CSSProperties
                    }
                  >
                    <div>
                      <span className="timer-phase">
                        {timer?.phase === "break" ? (
                          <>
                            <Coffee size={16} /> Take a breath
                          </>
                        ) : (
                          <>
                            <Leaf size={16} /> Focus time
                          </>
                        )}
                      </span>
                      <span className="digits" aria-label="Time remaining">
                        {clock(timer?.remaining ?? quick.focus_minutes * 60)}
                      </span>
                      <span className="timer-caption">
                        {timer
                          ? timer.paused
                            ? "Resume whenever you’re ready"
                            : "You’re right where you need to be"
                          : "Your next good session starts here"}
                      </span>
                    </div>
                  </div>
                  <h2 className="intention">{timer?.title ?? quick.title}</h2>
                  <div className="rounds" aria-label="Session progress">
                    {Array.from(
                      {
                        length: Math.min(timer?.sessions ?? quick.sessions, 12),
                      },
                      (_, i) => (
                        <span
                          key={i}
                          className={
                            i < (timer?.session_index ?? 1) ? "filled" : ""
                          }
                        />
                      ),
                    )}
                    {(timer?.sessions ?? quick.sessions) > 12 && (
                      <small>+{(timer?.sessions ?? quick.sessions) - 12}</small>
                    )}
                  </div>
                  <div className="timer-controls">
                    {timer ? (
                      <>
                        <button
                          className="secondary"
                          title="Stop and save partial progress"
                          disabled={busy}
                          onClick={() =>
                            void perform(
                              "timer_action",
                              { action: "stop" },
                              "Session stopped. Your focused time has been saved.",
                            )
                          }
                        >
                          <Square size={16} />
                          Stop
                        </button>
                        <button
                          className="primary large"
                          disabled={busy}
                          onClick={() =>
                            action(timer.paused ? "resume" : "pause")
                          }
                        >
                          {timer.paused ? (
                            <Play size={18} />
                          ) : (
                            <Pause size={18} />
                          )}
                          {timer.paused ? "Resume" : "Pause"}
                        </button>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() => action("skip")}
                        >
                          <SkipForward size={17} />
                          {timer.phase === "break"
                            ? "Skip break"
                            : "Next round"}
                        </button>
                      </>
                    ) : (
                      <button
                        className="primary large"
                        disabled={!data || busy}
                        onClick={() => void start()}
                      >
                        <Play size={18} fill="currentColor" />
                        Start focus session
                      </button>
                    )}
                  </div>
                  <p className="timer-footnote">
                    {timer
                      ? "Your progress is saved locally as you go."
                      : `${quick.focus_minutes} min focus · ${quick.break_minutes} min break · ${quick.final_break ? "Includes final break" : "No final break"}`}
                  </p>
                </section>
                <div className="focus-side">
                  <section className="card intention-card">
                    <span className="section-kicker">YOUR INTENTION</span>
                    <h2>What’s on your mind?</h2>
                    <p>Give this session a little direction.</p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void start();
                      }}
                    >
                      <fieldset disabled={!!timer || busy || !data}>
                        <label>
                          Session name
                          <input
                            required
                            maxLength={160}
                            value={quick.title}
                            onChange={(e) =>
                              setQuick({ ...quick, title: e.target.value })
                            }
                            placeholder="What will you work on?"
                          />
                        </label>
                        <PlanFields value={quick} onChange={setQuick} />
                      </fieldset>
                    </form>
                    <div className="tip">
                      <Leaf size={17} />
                      <span>
                        Close a few tabs. Get some water.
                        <br />
                        Make this time your own.
                      </span>
                    </div>
                  </section>
                  <section className="card today-summary">
                    <span className="section-kicker">TODAY, SO FAR</span>
                    <div className="today-numbers">
                      <div>
                        <strong>
                          {Math.floor((todayStats?.focus_seconds ?? 0) / 60)}
                          <small> min</small>
                        </strong>
                        <span>time focused</span>
                      </div>
                      <div>
                        <strong>
                          {todayStats?.sessions ?? 0}
                          <small> rounds</small>
                        </strong>
                        <span>little wins</span>
                      </div>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => setPage("progress")}
                    >
                      See your progress
                      <ArrowUpRight size={15} />
                    </button>
                  </section>
                </div>
              </div>
              <section className="card today-tasks">
                <div className="section-heading">
                  <div>
                    <h2>
                      On your list today{" "}
                      <span className="inline-count">{todayTasks.length}</span>
                    </h2>
                    <p>A little structure goes a long way.</p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => setPage("tasks")}
                  >
                    All tasks
                    <ArrowUpRight size={15} />
                  </button>
                </div>
                {todayTasks.length ? (
                  todayTasks.slice(0, 4).map(taskRow)
                ) : (
                  <div className="empty compact">
                    <ListTodo size={24} />
                    <span>
                      A fresh page. Add something you’d like to focus on.
                    </span>
                    <button
                      className="text-button"
                      disabled={!data}
                      onClick={() => setEditor(blank(data?.preferences))}
                    >
                      Add a task
                      <Plus size={15} />
                    </button>
                  </div>
                )}
              </section>
            </>
          )}

          {page === "tasks" && (
            <>
              <div className="task-toolbar">
                <label className="search">
                  <Search size={17} />
                  <input
                    aria-label="Search tasks"
                    placeholder="Find a task…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <select
                  aria-label="Task status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="all">All tasks</option>
                  <option value="pending">Pending</option>
                  <option value="completed">Completed</option>
                </select>
                <select
                  aria-label="Task priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  <option value="all">All priorities</option>
                  <option value="2">High</option>
                  <option value="1">Normal</option>
                  <option value="0">Low</option>
                </select>
              </div>
              {deleted !== null && (
                <div className="banner">
                  <span>Task moved out of your list.</span>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={async () => {
                      if (
                        await perform(
                          "delete_task",
                          { id: deleted, restore: true },
                          "Task restored.",
                        )
                      )
                        setDeleted(null);
                    }}
                  >
                    <RotateCcw size={14} />
                    Undo delete
                  </button>
                </div>
              )}
              {selectedTasks.map(([date, tasks]) => (
                <details
                  key={date}
                  className="card date-group"
                  open={date === today || undefined}
                >
                  <summary>
                    <ChevronRight size={18} />
                    <span>{dateLabel(date, today)}</span>
                    <span className="inline-count">{tasks.length}</span>
                    <small>
                      {tasks.filter((t) => t.completed).length} completed
                    </small>
                  </summary>
                  {tasks.map(taskRow)}
                </details>
              ))}
              {!selectedTasks.length && (
                <section className="card empty">
                  <ListTodo size={36} />
                  <h2>
                    {search || status !== "all" || priority !== "all"
                      ? "No matching tasks"
                      : "Start with one small thing."}
                  </h2>
                  <p>
                    {search
                      ? "Try another search or filter."
                      : "Plan a task, choose its rhythm, and make room to focus."}
                  </p>
                  <button
                    className="primary"
                    disabled={!data || busy}
                    onClick={() => setEditor(blank(data?.preferences))}
                  >
                    <Plus size={16} />
                    Add a task
                  </button>
                </section>
              )}
            </>
          )}

          {page === "progress" && (
            <>
              <div className="stat-grid">
                {[
                  {
                    title: "Focused today",
                    value: `${Math.floor((todayStats?.focus_seconds ?? 0) / 60)} min`,
                    icon: TimerIcon,
                  },
                  {
                    title: "Sessions completed",
                    value: todayStats?.sessions ?? 0,
                    icon: Check,
                  },
                  {
                    title: "Tasks completed",
                    value: todayStats?.tasks ?? 0,
                    icon: ListTodo,
                  },
                ].map((stat) => (
                  <section className="card stat" key={stat.title}>
                    <stat.icon size={20} />
                    <span>{stat.title}</span>
                    <strong>{stat.value}</strong>
                  </section>
                ))}
              </div>
              <section className="card week-card">
                <div className="section-heading">
                  <div>
                    <h2>Your week in focus</h2>
                    <p>
                      Actual focused minutes. Breaks and sleep aren’t counted.
                    </p>
                  </div>
                  <span className="pill">LAST 7 DAYS</span>
                </div>
                <div className="week-bars">
                  {(data?.stats ?? []).map((day) => (
                    <div className="day-bar" key={day.date}>
                      <span>{Math.floor(day.focus_seconds / 60)}m</span>
                      <div className="bar-track">
                        <div
                          style={{
                            height: `${Math.max(day.focus_seconds > 0 ? 3 : 0, (day.focus_seconds / Math.max(60, ...(data?.stats.map((d) => d.focus_seconds) ?? [60]))) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className={day.date === today ? "today" : ""}>
                        {day.date === today
                          ? "Today"
                          : new Date(`${day.date}T12:00:00`).toLocaleDateString(
                              undefined,
                              { weekday: "short" },
                            )}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
              <section className="card history">
                <div className="section-heading">
                  <div>
                    <h2>Session history</h2>
                    <p>Your last 50 sessions, including partial work.</p>
                  </div>
                </div>
                {data?.history.length ? (
                  data.history.map((run) => (
                    <div className="history-row" key={run.id}>
                      <span className="history-icon">
                        <Leaf size={17} />
                      </span>
                      <div>
                        <strong>{run.title}</strong>
                        <span>{new Date(run.started_at).toLocaleString()}</span>
                      </div>
                      <span>{Math.floor(run.focus_seconds / 60)}m focused</span>
                      <span>
                        {run.completed_sessions}/{run.sessions} rounds
                      </span>
                      <span
                        className={`pill ${run.status === "completed" ? "completed" : ""}`}
                      >
                        {run.status}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="empty compact">
                    Your first session is a fresh start. You’ll see it here.
                  </div>
                )}
              </section>
            </>
          )}

          {page === "settings" && (
            <div className="settings-layout">
              <section className="card settings-card">
                <h2>Your default rhythm</h2>
                <p>New tasks and quick sessions start with these settings.</p>
                <form onSubmit={savePreferences}>
                  <fieldset disabled={!data || busy}>
                    <PlanFields
                      value={{ ...prefs, title: "Defaults" }}
                      onChange={(v) => setPrefs({ ...prefs, ...v })}
                    />
                    <div className="setting-divider" />
                    <label className="setting-toggle">
                      <span>
                        <strong>Desktop notifications</strong>
                        <small>
                          A gentle nudge when focus and break phases change.
                        </small>
                      </span>
                      <input
                        type="checkbox"
                        checked={prefs.notifications}
                        onChange={(e) =>
                          setPrefs({
                            ...prefs,
                            notifications: e.target.checked,
                          })
                        }
                      />
                    </label>
                    <label className="setting-toggle">
                      <span>
                        <strong>Session sounds</strong>
                        <small>
                          A short sound at the start and phase transitions.
                        </small>
                      </span>
                      <input
                        type="checkbox"
                        checked={prefs.sound}
                        onChange={(e) =>
                          setPrefs({ ...prefs, sound: e.target.checked })
                        }
                      />
                    </label>
                    <button className="primary" type="submit">
                      <Check size={16} />
                      Save preferences
                    </button>
                  </fieldset>
                </form>
                <button
                  className="text-button notification-test"
                  disabled={!data || busy}
                  onClick={async () => {
                    try {
                      if (
                        !(await isPermissionGranted()) &&
                        (await requestPermission()) !== "granted"
                      )
                        throw new Error(
                          "Notification permission was not granted.",
                        );
                      sendNotification({
                        title: "FocusNest",
                        body: "Your notifications are ready. Make room for focus.",
                      });
                      setNotice("Test notification sent.");
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  <Bell size={16} />
                  Send test notification
                </button>
              </section>
              <section className="card settings-card">
                <span className="section-kicker">LOCAL FIRST. ALWAYS.</span>
                <h2>Your work stays yours.</h2>
                <p>
                  Tasks, history, and timer progress live in SQLite on this
                  device. No account. No cloud required.
                </p>
                <label className="path-label">
                  Your database
                  <code>
                    {data?.database_path ?? "Available in the desktop app"}
                  </code>
                </label>
                <div className="setting-divider" />
                <h3>Bring your tasks with you</h3>
                <p>
                  Import a version-1 database from the Python app into an empty
                  Rust workspace. The original file is never modified. Close the
                  Python app first for a stable timer checkpoint.
                </p>
                <button
                  className="secondary"
                  disabled={!data || busy || !!timer}
                  onClick={async () => {
                    setImportOpen(!importOpen);
                    try {
                      const paths = await invoke<string[]>("legacy_paths");
                      if (!legacyPath && paths.length) setLegacyPath(paths[0]);
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  Import Python database
                  <ArrowUpRight size={15} />
                </button>
                {importOpen && (
                  <form
                    className="import-form"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (
                        await perform(
                          "import_legacy",
                          { path: legacyPath },
                          "Tasks and history imported. Any recovered timer is paused.",
                        )
                      ) {
                        loadedDefaults.current = false;
                        await reload();
                        setImportOpen(false);
                      }
                    }}
                  >
                    <label>
                      Database file path
                      <input
                        required
                        value={legacyPath}
                        onChange={(e) => setLegacyPath(e.target.value)}
                        placeholder="/path/to/study_timer.sqlite3"
                      />
                    </label>
                    <button className="primary" disabled={busy || !data}>
                      Import a copy
                    </button>
                  </form>
                )}
                <p className="fine-print">
                  FocusNest 0.3.0 · Rust + Tauri
                  <br />A separate app and data directory during migration.
                </p>
              </section>
            </div>
          )}
        </div>
      </main>
      <dialog
        ref={dialog}
        onCancel={() => setEditor(null)}
        onClose={() => setEditor(null)}
      >
        <div className="modal-header">
          <div>
            <span className="eyebrow">ONE THING AT A TIME</span>
            <h2>
              {editor?.id ? "Edit your task" : "A little plan for your day"}
            </h2>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Close task editor"
            onClick={() => setEditor(null)}
          >
            <X size={20} />
          </button>
        </div>
        {editor && (
          <form onSubmit={saveTask}>
            <fieldset disabled={busy}>
              <label>
                What would you like to do?
                <input
                  autoFocus
                  required
                  maxLength={160}
                  placeholder="e.g. Read a chapter"
                  value={editor.title}
                  onChange={(e) =>
                    setEditor({ ...editor, title: e.target.value })
                  }
                />
              </label>
              <div className="form-pair">
                <label>
                  Planned date
                  <input
                    type="date"
                    required
                    value={editor.planned_date}
                    onChange={(e) =>
                      setEditor({ ...editor, planned_date: e.target.value })
                    }
                  />
                </label>
                <label>
                  Priority
                  <select
                    value={editor.priority}
                    onChange={(e) =>
                      setEditor({ ...editor, priority: Number(e.target.value) })
                    }
                  >
                    <option value="0">Low</option>
                    <option value="1">Normal</option>
                    <option value="2">High</option>
                  </select>
                </label>
              </div>
              <PlanFields
                value={editor}
                onChange={(v) => setEditor({ ...editor, ...v })}
              />
              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setEditor(null)}
                >
                  Cancel
                </button>
                <button className="primary" type="submit">
                  <Check size={16} />
                  {editor.id ? "Save changes" : "Create task"}
                </button>
              </div>
            </fieldset>
          </form>
        )}
        {error && (
          <p className="modal-error" role="alert">
            {error}
          </p>
        )}
      </dialog>
    </div>
  );
}
