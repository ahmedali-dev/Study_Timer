use crate::{model::*, store};
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection, OpenFlags};
use serde::Serialize;
use std::{
    path::{Path, PathBuf},
    time::Instant,
};

pub struct Runtime {
    pub db: Connection,
    pub path: PathBuf,
    pub timer: Option<Timer>,
    last_tick: Instant,
    last_wall: DateTime<Utc>,
}
#[derive(Serialize)]
pub struct Snapshot {
    pub tasks: Vec<Task>,
    pub timer: Option<Timer>,
    pub stats: Vec<DayStats>,
    pub history: Vec<History>,
    pub preferences: Preferences,
    pub database_path: String,
    pub today: String,
}
#[derive(Default)]
pub struct Update {
    pub changed: bool,
    pub message: Option<String>,
}
impl Runtime {
    pub fn open(path: PathBuf) -> AppResult<Self> {
        let db = store::open(&path)?;
        let timer = store::active(&db)?;
        if let Some(t) = &timer {
            db.execute(
                "UPDATE active_timer SET state=? WHERE id=1",
                [serde_json::to_string(t).map_err(|e| e.to_string())?],
            )
            .map_err(|e| e.to_string())?;
        }
        Ok(Self {
            db,
            path,
            timer,
            last_tick: Instant::now(),
            last_wall: Utc::now(),
        })
    }
    pub fn snapshot(&self) -> AppResult<Snapshot> {
        Ok(Snapshot {
            tasks: store::tasks(&self.db)?,
            timer: self.timer.clone(),
            stats: store::stats(&self.db)?,
            history: store::history(&self.db)?,
            preferences: store::preferences(&self.db)?,
            database_path: self.path.display().to_string(),
            today: today(),
        })
    }
    fn reset_clock(&mut self) {
        self.last_tick = Instant::now();
        self.last_wall = Utc::now();
    }
    pub fn start(&mut self, mut plan: Plan, task_id: Option<i64>) -> AppResult<()> {
        if self.timer.is_some() {
            return Err("Finish or stop the current session first.".into());
        }
        if let Some(id) = task_id {
            let task = store::tasks(&self.db)?
                .into_iter()
                .find(|t| t.id == id && !t.completed)
                .ok_or("This task is completed or no longer exists.")?;
            plan = Plan {
                title: task.title,
                focus_minutes: task.focus_minutes,
                break_minutes: task.break_minutes,
                sessions: task.sessions,
                final_break: task.final_break,
            };
        }
        plan.validate()?;
        let t = Timer {
            run_id: uuid::Uuid::new_v4().to_string(),
            task_id,
            title: plan.title.trim().into(),
            focus_minutes: plan.focus_minutes,
            break_minutes: plan.break_minutes,
            sessions: plan.sessions,
            final_break: plan.final_break,
            phase: "focus".into(),
            session_index: 1,
            remaining: (plan.focus_minutes * 60) as f64,
            paused: false,
            skipped: false,
            started_at: Utc::now().to_rfc3339(),
        };
        let tx = self.db.transaction().map_err(|e| e.to_string())?;
        tx.execute(
            "INSERT INTO timer_runs VALUES(?,?,?,?,?,?,?,?,?,NULL)",
            params![
                t.run_id,
                t.task_id,
                t.title,
                t.focus_minutes,
                t.break_minutes,
                t.sessions,
                t.final_break,
                "active",
                t.started_at
            ],
        )
        .map_err(|e| e.to_string())?;
        tx.execute(
            "INSERT INTO active_timer VALUES(1,?)",
            [serde_json::to_string(&t).map_err(|e| e.to_string())?],
        )
        .map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())?;
        self.timer = Some(t);
        self.reset_clock();
        Ok(())
    }
    pub fn tick(&mut self) -> AppResult<Update> {
        let instant = Instant::now();
        let wall = Utc::now();
        let elapsed = instant.duration_since(self.last_tick).as_secs_f64();
        let wall_elapsed = (wall - self.last_wall).num_milliseconds() as f64 / 1000.0;
        self.last_tick = instant;
        self.last_wall = wall;
        self.tick_elapsed(elapsed, wall_elapsed, wall)
    }
    fn tick_elapsed(
        &mut self,
        elapsed: f64,
        wall_elapsed: f64,
        wall: DateTime<Utc>,
    ) -> AppResult<Update> {
        let Some(before) = self.timer.clone() else {
            return Ok(Update::default());
        };
        if before.paused {
            return Ok(Update::default());
        }
        let mut next = before.clone();
        let mut transition = Transition::default();
        let mut update = Update::default();
        let mut credited = 0.0;
        if elapsed > 10.0 || wall_elapsed > 10.0 || wall_elapsed < -1.0 {
            next.paused = true;
            update.message = Some("Timer paused after sleep or a clock change.".into());
            update.changed = true;
        } else {
            credited = elapsed.max(0.0).min(next.remaining);
            next.remaining = (next.remaining - credited).max(0.0);
            if next.remaining <= 0.0 {
                transition = next.advance(false);
                update.changed = true;
                update.message = Some(match transition.outcome {
                    Some("completed") => "Session complete. Well done!".into(),
                    Some(_) => "Session finished.".into(),
                    None if next.phase == "break" => "Time for a break.".into(),
                    None => format!("Focus round {} is ready.", next.session_index),
                });
            }
        }
        let tx = self.db.transaction().map_err(|e| e.to_string())?;
        store::persist(&tx, &next, &before, &transition, credited, wall)?;
        tx.commit().map_err(|e| e.to_string())?;
        self.timer = if transition.outcome.is_some() {
            None
        } else {
            Some(next)
        };
        Ok(update)
    }
    pub fn action(&mut self, action: &str) -> AppResult<()> {
        if !["pause", "resume", "skip", "stop"].contains(&action) {
            return Err("Unknown timer action.".into());
        }
        let phase = self
            .timer
            .as_ref()
            .map(|t| (t.phase.clone(), t.session_index));
        self.tick()?;
        let Some(before) = self.timer.clone() else {
            return Ok(());
        };
        // If the tick advanced naturally, do not skip an additional phase.
        if action == "skip" && phase != Some((before.phase.clone(), before.session_index)) {
            return Ok(());
        }
        let mut next = before.clone();
        let mut transition = Transition::default();
        match action {
            "pause" => next.paused = true,
            "resume" => next.paused = false,
            "skip" => transition = next.advance(before.phase == "focus"),
            "stop" => {
                transition = Transition {
                    session_result: if before.phase == "focus" {
                        Some("partial")
                    } else {
                        None
                    },
                    outcome: Some("interrupted"),
                }
            }
            _ => unreachable!(),
        }
        let tx = self.db.transaction().map_err(|e| e.to_string())?;
        store::persist(&tx, &next, &before, &transition, 0.0, Utc::now())?;
        tx.commit().map_err(|e| e.to_string())?;
        self.timer = if transition.outcome.is_some() {
            None
        } else {
            Some(next)
        };
        self.reset_clock();
        Ok(())
    }
    pub fn import_legacy(&mut self, path: &Path) -> AppResult<()> {
        let count: i64 = self
            .db
            .query_row(
                "SELECT (SELECT COUNT(*) FROM tasks)+(SELECT COUNT(*) FROM timer_runs)",
                [],
                |r| r.get(0),
            )
            .map_err(|e| e.to_string())?;
        if count > 0 || self.timer.is_some() {
            return Err("Import is allowed only into an empty Rust database. Your current work was not changed.".into());
        }
        if path.canonicalize().map_err(|e| e.to_string())?
            == self.path.canonicalize().map_err(|e| e.to_string())?
        {
            return Err("Choose the Python database, not the current database.".into());
        }
        let source = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
            .map_err(|e| e.to_string())?;
        let version: i64 = source
            .pragma_query_value(None, "user_version", |r| r.get(0))
            .map_err(|e| e.to_string())?;
        if version != 1 {
            return Err("Import requires a version-1 FocusNest database. Open older databases with the Python app first.".into());
        }
        // Validate required data before replacing even an empty destination.
        store::tasks(&source)?;
        store::history(&source)?;
        store::preferences(&source)?;
        let recovered = store::active(&source)?;
        rusqlite::backup::Backup::new(&source, &mut self.db)
            .map_err(|e| e.to_string())?
            .run_to_completion(128, std::time::Duration::from_millis(10), None)
            .map_err(|e| e.to_string())?;
        self.timer = recovered;
        if let Some(timer) = &self.timer {
            self.db
                .execute(
                    "UPDATE active_timer SET state=? WHERE id=1",
                    [serde_json::to_string(timer).map_err(|e| e.to_string())?],
                )
                .map_err(|e| e.to_string())?;
        }
        self.reset_clock();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn runtime() -> (tempfile::TempDir, Runtime) {
        let dir = tempfile::tempdir().unwrap();
        let r = Runtime::open(dir.path().join("test.sqlite3")).unwrap();
        (dir, r)
    }
    fn plan() -> Plan {
        Plan {
            title: "Test".into(),
            focus_minutes: 1,
            break_minutes: 0,
            sessions: 1,
            final_break: false,
        }
    }
    #[test]
    fn start_pause_recover_preserves_progress() {
        let (dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        r.tick_elapsed(2.0, 2.0, Utc::now()).unwrap();
        r.action("pause").unwrap();
        assert!(r.timer.as_ref().unwrap().remaining <= 58.0);
        drop(r);
        let r = Runtime::open(dir.path().join("test.sqlite3")).unwrap();
        assert!(r.timer.unwrap().paused);
    }
    #[test]
    fn sleep_is_not_credited() {
        let (_dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        r.tick_elapsed(60.0, 60.0, Utc::now()).unwrap();
        assert!(r.timer.as_ref().unwrap().paused);
        assert_eq!(r.timer.as_ref().unwrap().remaining, 60.0);
        assert_eq!(store::history(&r.db).unwrap()[0].focus_seconds, 0.0);
    }
    #[test]
    fn credits_only_remaining_focus() {
        let (_dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        r.timer.as_mut().unwrap().remaining = 0.5;
        r.tick_elapsed(1.0, 1.0, Utc::now()).unwrap();
        assert!(r.timer.is_none());
        assert_eq!(store::history(&r.db).unwrap()[0].focus_seconds, 0.5);
        assert_eq!(store::history(&r.db).unwrap()[0].status, "completed");
    }
    #[test]
    fn only_one_active_timer() {
        let (_dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        assert!(r.start(plan(), None).is_err());
    }
    #[test]
    fn stop_clears_checkpoint_and_preserves_partial_work() {
        let (_dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        r.tick_elapsed(4.0, 4.0, Utc::now()).unwrap();
        r.action("stop").unwrap();
        assert!(r.timer.is_none());
        assert!(store::active(&r.db).unwrap().is_none());
        let history = store::history(&r.db).unwrap();
        assert_eq!(history[0].status, "interrupted");
        assert!(history[0].focus_seconds >= 4.0);
        assert_eq!(history[0].completed_sessions, 0);
        r.start(plan(), None).unwrap();
    }
    #[test]
    fn import_is_copy_not_shared_database() {
        let (_dir, mut destination) = runtime();
        let (_source_dir, mut source) = runtime();
        source.start(plan(), None).unwrap();
        destination.import_legacy(&source.path).unwrap();
        assert!(destination.timer.as_ref().unwrap().paused);
        destination.action("stop").unwrap();
        assert!(store::active(&source.db).unwrap().is_some());
        assert!(destination.import_legacy(&source.path).is_err());
    }
    #[test]
    fn persistence_failure_does_not_advance_in_memory() {
        let (_dir, mut r) = runtime();
        r.start(plan(), None).unwrap();
        r.db.execute_batch("DROP TABLE focus_intervals").unwrap();
        assert!(r.tick_elapsed(1.0, 1.0, Utc::now()).is_err());
        assert_eq!(r.timer.unwrap().remaining, 60.0);
    }
    #[test]
    fn finished_focus_completes_task_but_skip_does_not() {
        for skipped in [false, true] {
            let (_dir, mut r) = runtime();
            store::save_task(
                &r.db,
                TaskInput {
                    id: None,
                    plan: plan(),
                    planned_date: today(),
                    priority: 1,
                },
            )
            .unwrap();
            let task = store::tasks(&r.db).unwrap().remove(0);
            r.start(plan(), Some(task.id)).unwrap();
            if skipped {
                r.action("skip").unwrap();
            } else {
                r.timer.as_mut().unwrap().remaining = 0.1;
                r.tick_elapsed(1.0, 1.0, Utc::now()).unwrap();
            }
            assert_eq!(store::tasks(&r.db).unwrap()[0].completed, !skipped);
        }
    }
    #[test]
    fn imported_python_checkpoint_is_paused_and_keeps_fields() {
        let (_dir, mut destination) = runtime();
        let (_source_dir, source) = runtime();
        source.db.execute("INSERT INTO active_timer VALUES(1,?)", [r#"{"run_id":"python-run","task_id":null,"title":"Python session","focus_minutes":50,"break_minutes":10,"sessions":4,"final_break":true,"phase":"break","session_index":2,"remaining":123.25,"paused":false,"skipped":false,"started_at":"2026-10-18T10:00:00+00:00"}"#]).unwrap();
        destination.import_legacy(&source.path).unwrap();
        let timer = destination.timer.unwrap();
        assert_eq!(timer.remaining, 123.25);
        assert_eq!(timer.session_index, 2);
        assert_eq!(timer.phase, "break");
        assert!(timer.paused);
        let raw: String = source
            .db
            .query_row("SELECT state FROM active_timer", [], |r| r.get(0))
            .unwrap();
        assert!(!serde_json::from_str::<Timer>(&raw).unwrap().paused);
    }
    #[test]
    fn unsupported_import_does_not_replace_empty_destination() {
        let (_dir, mut destination) = runtime();
        let (_source_dir, source) = runtime();
        source.db.pragma_update(None, "user_version", 99).unwrap();
        assert!(destination.import_legacy(&source.path).is_err());
        assert_eq!(
            destination
                .db
                .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
                .unwrap(),
            1
        );
        destination.start(plan(), None).unwrap();
    }
}
