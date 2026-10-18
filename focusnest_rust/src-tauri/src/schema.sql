CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
 focus_minutes INTEGER NOT NULL CHECK(focus_minutes>0), break_minutes INTEGER NOT NULL CHECK(break_minutes>=0),
 sessions INTEGER NOT NULL CHECK(sessions>0), completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN(0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, deleted_at TEXT, planned_date TEXT,
 priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 0 AND 2), final_break INTEGER NOT NULL DEFAULT 1 CHECK(final_break IN(0,1)));
CREATE INDEX IF NOT EXISTS tasks_plan_idx ON tasks(planned_date,completed,priority);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS timer_runs(id TEXT PRIMARY KEY,task_id INTEGER,title TEXT NOT NULL,focus_minutes INTEGER NOT NULL,break_minutes INTEGER NOT NULL,sessions INTEGER NOT NULL,final_break INTEGER NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT);
CREATE TABLE IF NOT EXISTS active_timer(id INTEGER PRIMARY KEY CHECK(id=1),state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS focus_sessions(run_id TEXT NOT NULL,session_index INTEGER NOT NULL,status TEXT NOT NULL,ended_at TEXT NOT NULL,PRIMARY KEY(run_id,session_index));
CREATE TABLE IF NOT EXISTS focus_intervals(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,session_index INTEGER NOT NULL,started_at TEXT NOT NULL,ended_at TEXT NOT NULL,seconds REAL NOT NULL CHECK(seconds>=0));
CREATE INDEX IF NOT EXISTS focus_intervals_date_idx ON focus_intervals(ended_at);
CREATE INDEX IF NOT EXISTS timer_runs_task_idx ON timer_runs(task_id,started_at);
CREATE TABLE IF NOT EXISTS task_completions(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL,completed_at TEXT NOT NULL,reversed INTEGER NOT NULL DEFAULT 0);
PRAGMA user_version=1;
