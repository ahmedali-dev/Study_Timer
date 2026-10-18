use crate::model::*;
use chrono::{DateTime, Days, Local, NaiveDateTime, TimeZone, Utc};
use rusqlite::{params, Connection, OptionalExtension, Transaction};
use std::{collections::BTreeMap, path::Path};

pub fn open(path: &Path) -> AppResult<Connection> {
    let mut db = Connection::open(path).map_err(|e| e.to_string())?;
    db.busy_timeout(std::time::Duration::from_secs(5))
        .map_err(|e| e.to_string())?;
    let version: i64 = db
        .pragma_query_value(None, "user_version", |r| r.get(0))
        .map_err(|e| e.to_string())?;
    let tables: i64 = db
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'",
            [],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    if version > 1 || (version == 0 && tables > 0) {
        return Err("Unsupported database version. Upgrade it with the Python app first; no data was changed.".into());
    }
    let tx = db.transaction().map_err(|e| e.to_string())?;
    tx.execute_batch(include_str!("schema.sql"))
        .map_err(|e| e.to_string())?;
    tx.commit().map_err(|e| e.to_string())?;
    Ok(db)
}
pub fn active(db: &Connection) -> AppResult<Option<Timer>> {
    let text: Option<String> = db
        .query_row("SELECT state FROM active_timer WHERE id=1", [], |r| {
            r.get(0)
        })
        .optional()
        .map_err(|e| e.to_string())?;
    text.map(|text| {
        let mut timer: Timer =
            serde_json::from_str(&text).map_err(|e| format!("Cannot recover saved timer: {e}"))?;
        timer.validate()?;
        timer.paused = true;
        Ok(timer)
    })
    .transpose()
}
pub fn tasks(db: &Connection) -> AppResult<Vec<Task>> {
    let mut q=db.prepare("SELECT id,title,focus_minutes,break_minutes,sessions,final_break,COALESCE(planned_date,date(created_at,'localtime')),priority,completed,(SELECT COUNT(*) FROM focus_sessions WHERE status='completed' AND run_id=(SELECT id FROM timer_runs WHERE task_id=tasks.id ORDER BY started_at DESC LIMIT 1)) FROM tasks WHERE deleted_at IS NULL ORDER BY planned_date DESC,completed,priority DESC,id DESC").map_err(|e|e.to_string())?;
    let rows = q
        .query_map([], |r| {
            Ok(Task {
                id: r.get(0)?,
                title: r.get(1)?,
                focus_minutes: r.get(2)?,
                break_minutes: r.get(3)?,
                sessions: r.get(4)?,
                final_break: r.get(5)?,
                planned_date: r.get(6)?,
                priority: r.get(7)?,
                completed: r.get(8)?,
                completed_rounds: r.get(9)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}
pub fn save_task(db: &Connection, input: TaskInput) -> AppResult<()> {
    input.validate()?;
    let p = input.plan;
    if let Some(id) = input.id {
        let n=db.execute("UPDATE tasks SET title=?1,focus_minutes=?2,break_minutes=?3,sessions=?4,final_break=?5,planned_date=?6,priority=?7 WHERE id=?8 AND deleted_at IS NULL", params![p.title.trim(),p.focus_minutes,p.break_minutes,p.sessions,p.final_break,input.planned_date,input.priority,id]).map_err(|e|e.to_string())?;
        if n == 0 {
            return Err("Task no longer exists.".into());
        }
    } else {
        db.execute("INSERT INTO tasks(title,focus_minutes,break_minutes,sessions,final_break,planned_date,priority) VALUES(?,?,?,?,?,?,?)", params![p.title.trim(),p.focus_minutes,p.break_minutes,p.sessions,p.final_break,input.planned_date,input.priority]).map_err(|e|e.to_string())?;
    }
    Ok(())
}
pub fn complete(tx: &Transaction<'_>, id: i64, completed: bool) -> AppResult<()> {
    let previous: bool = tx
        .query_row(
            "SELECT completed FROM tasks WHERE id=? AND deleted_at IS NULL",
            [id],
            |r| r.get(0),
        )
        .map_err(|_| "Task no longer exists.")?;
    tx.execute(
        "UPDATE tasks SET completed=? WHERE id=?",
        params![completed, id],
    )
    .map_err(|e| e.to_string())?;
    if completed && !previous {
        tx.execute(
            "INSERT INTO task_completions(task_id,completed_at) VALUES(?,?)",
            params![id, Utc::now().to_rfc3339()],
        )
        .map_err(|e| e.to_string())?;
    } else if !completed {
        tx.execute(
            "UPDATE task_completions SET reversed=1 WHERE task_id=?",
            [id],
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}
pub fn persist(
    tx: &Transaction<'_>,
    timer: &Timer,
    before: &Timer,
    transition: &Transition,
    credited: f64,
    wall: DateTime<Utc>,
) -> AppResult<()> {
    let now = wall.to_rfc3339();
    if credited > 0.0 && before.phase == "focus" {
        let start = wall - chrono::Duration::microseconds((credited * 1_000_000.0) as i64);
        tx.execute(
            "INSERT INTO focus_intervals VALUES(?,?,?,?,?,?)",
            params![
                uuid::Uuid::new_v4().to_string(),
                before.run_id,
                before.session_index,
                start.to_rfc3339(),
                now,
                credited
            ],
        )
        .map_err(|e| e.to_string())?;
    }
    if let Some(result) = transition.session_result {
        tx.execute(
            "INSERT OR REPLACE INTO focus_sessions VALUES(?,?,?,?)",
            params![before.run_id, before.session_index, result, now],
        )
        .map_err(|e| e.to_string())?;
    }
    if let Some(outcome) = transition.outcome {
        tx.execute(
            "UPDATE timer_runs SET status=?,ended_at=? WHERE id=?",
            params![outcome, now, timer.run_id],
        )
        .map_err(|e| e.to_string())?;
        tx.execute("DELETE FROM active_timer WHERE id=1", [])
            .map_err(|e| e.to_string())?;
        if outcome == "completed" && !timer.skipped {
            if let Some(id) = timer.task_id {
                let exists: bool = tx
                    .query_row(
                        "SELECT EXISTS(SELECT 1 FROM tasks WHERE id=? AND deleted_at IS NULL)",
                        [id],
                        |r| r.get(0),
                    )
                    .map_err(|e| e.to_string())?;
                if exists {
                    complete(tx, id, true)?;
                }
            }
        }
    } else {
        tx.execute(
            "INSERT OR REPLACE INTO active_timer VALUES(1,?)",
            [serde_json::to_string(timer).map_err(|e| e.to_string())?],
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}
pub fn preferences(db: &Connection) -> AppResult<Preferences> {
    let raw: Option<String> = db
        .query_row(
            "SELECT value FROM settings WHERE key='rust_preferences'",
            [],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if let Some(raw) = raw {
        return serde_json::from_str(&raw).map_err(|e| e.to_string());
    }
    let mut prefs = Preferences::default();
    // Legacy values are JSON strings, not bare numbers.
    for (key, target) in [
        ("study", &mut prefs.focus_minutes),
        ("break", &mut prefs.break_minutes),
        ("session", &mut prefs.sessions),
    ] {
        let raw: Option<String> = db
            .query_row("SELECT value FROM settings WHERE key=?", [key], |r| {
                r.get(0)
            })
            .optional()
            .map_err(|e| e.to_string())?;
        if let Some(raw) = raw {
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(&raw) {
                if let Some(number) = value
                    .as_i64()
                    .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
                {
                    *target = number;
                }
            }
        }
    }
    let raw: Option<String> = db
        .query_row(
            "SELECT value FROM settings WHERE key='final_break'",
            [],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if let Some(raw) = raw {
        prefs.final_break = serde_json::from_str(&raw).unwrap_or(false);
    }
    Ok(prefs)
}
pub fn parse_date(value: &str) -> AppResult<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(value)
        .map(|d| d.with_timezone(&Utc))
        .or_else(|_| NaiveDateTime::parse_from_str(value, "%Y-%m-%d %H:%M:%S").map(|d| d.and_utc()))
        .map_err(|e| e.to_string())
}
pub fn stats(db: &Connection) -> AppResult<Vec<DayStats>> {
    let today = Local::now().date_naive();
    let mut days = BTreeMap::new();
    for i in 0..7 {
        let day = today.checked_sub_days(Days::new(i)).ok_or("Invalid date")?;
        days.insert(
            day.to_string(),
            DayStats {
                date: day.to_string(),
                ..Default::default()
            },
        );
    }
    let cutoff = today
        .checked_sub_days(Days::new(6))
        .ok_or("Invalid date")?
        .to_string();
    let mut q=db.prepare("SELECT started_at,ended_at,seconds FROM focus_intervals WHERE julianday(ended_at)>=julianday(?,'-1 day')").map_err(|e|e.to_string())?;
    let rows = q
        .query_map([&cutoff], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, f64>(2)?,
            ))
        })
        .map_err(|e| e.to_string())?;
    for row in rows {
        let (a, b, seconds) = row.map_err(|e| e.to_string())?;
        let (start, end) = (parse_date(&a)?, parse_date(&b)?);
        let span = (end - start).num_microseconds().unwrap_or(0) as f64 / 1_000_000.0;
        if span <= 0.0 {
            continue;
        }
        for day in days.values_mut() {
            let date = chrono::NaiveDate::parse_from_str(&day.date, "%Y-%m-%d")
                .map_err(|e| e.to_string())?;
            let first = Local
                .from_local_datetime(&date.and_hms_opt(0, 0, 0).unwrap())
                .earliest()
                .ok_or("Cannot resolve local midnight")?
                .with_timezone(&Utc);
            let next = date.succ_opt().ok_or("Invalid date")?;
            let last = Local
                .from_local_datetime(&next.and_hms_opt(0, 0, 0).unwrap())
                .earliest()
                .ok_or("Cannot resolve local midnight")?
                .with_timezone(&Utc);
            let overlap = (end.min(last) - start.max(first))
                .num_microseconds()
                .unwrap_or(0)
                .max(0) as f64
                / 1_000_000.0;
            day.focus_seconds += seconds * overlap / span;
        }
    }
    for (sql, kind) in [
        (
            "SELECT ended_at FROM focus_sessions WHERE status='completed'",
            0,
        ),
        (
            "SELECT completed_at FROM task_completions WHERE reversed=0",
            1,
        ),
    ] {
        let mut q = db.prepare(sql).map_err(|e| e.to_string())?;
        let rows = q
            .query_map([], |r| r.get::<_, String>(0))
            .map_err(|e| e.to_string())?;
        for row in rows {
            let key = parse_date(&row.map_err(|e| e.to_string())?)?
                .with_timezone(&Local)
                .format("%Y-%m-%d")
                .to_string();
            if let Some(day) = days.get_mut(&key) {
                if kind == 0 {
                    day.sessions += 1;
                } else {
                    day.tasks += 1;
                }
            }
        }
    }
    Ok(days.into_values().collect())
}
pub fn history(db: &Connection) -> AppResult<Vec<History>> {
    let mut q=db.prepare("SELECT id,title,status,started_at,COALESCE((SELECT SUM(seconds) FROM focus_intervals WHERE run_id=r.id),0),(SELECT COUNT(*) FROM focus_sessions WHERE run_id=r.id AND status='completed'),sessions FROM timer_runs r ORDER BY started_at DESC LIMIT 50").map_err(|e|e.to_string())?;
    let rows = q
        .query_map([], |r| {
            Ok(History {
                id: r.get(0)?,
                title: r.get(1)?,
                status: r.get(2)?,
                started_at: r.get(3)?,
                focus_seconds: r.get(4)?,
                completed_sessions: r.get(5)?,
                sessions: r.get(6)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn saves_and_validates_tasks() {
        let tmp = tempfile::tempdir().unwrap();
        let db = open(&tmp.path().join("test.sqlite3")).unwrap();
        let mut input = TaskInput {
            id: None,
            plan: Plan {
                title: " Work ".into(),
                focus_minutes: 25,
                break_minutes: 5,
                sessions: 4,
                final_break: false,
            },
            planned_date: today(),
            priority: 2,
        };
        save_task(&db, input.clone()).unwrap();
        assert_eq!(tasks(&db).unwrap()[0].title, "Work");
        input.plan.focus_minutes = 0;
        assert!(save_task(&db, input).is_err());
        assert_eq!(tasks(&db).unwrap().len(), 1);
    }
    #[test]
    fn newer_databases_remain_untouched() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("test.sqlite3");
        let db = Connection::open(&path).unwrap();
        db.pragma_update(None, "user_version", 99).unwrap();
        drop(db);
        assert!(open(&path).is_err());
        let db = Connection::open(path).unwrap();
        assert_eq!(
            db.pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
                .unwrap(),
            99
        );
    }
    #[test]
    fn completion_is_idempotent_and_reversible() {
        let mut db = Connection::open_in_memory().unwrap();
        db.execute_batch(include_str!("schema.sql")).unwrap();
        db.execute(
            "INSERT INTO tasks(title,focus_minutes,break_minutes,sessions) VALUES('Test',1,0,1)",
            [],
        )
        .unwrap();
        let tx = db.transaction().unwrap();
        complete(&tx, 1, true).unwrap();
        complete(&tx, 1, true).unwrap();
        tx.commit().unwrap();
        assert_eq!(stats(&db).unwrap().last().unwrap().tasks, 1);
        let tx = db.transaction().unwrap();
        complete(&tx, 1, false).unwrap();
        tx.commit().unwrap();
        assert_eq!(stats(&db).unwrap().last().unwrap().tasks, 0);
    }
    #[test]
    fn focus_spanning_local_midnight_is_split_without_inflation() {
        let db = Connection::open_in_memory().unwrap();
        db.execute_batch(include_str!("schema.sql")).unwrap();
        let day = Local::now().date_naive();
        let midnight = Local
            .from_local_datetime(&day.and_hms_opt(0, 0, 0).unwrap())
            .earliest()
            .unwrap()
            .with_timezone(&Utc);
        let start = midnight - chrono::Duration::minutes(10);
        let end = midnight + chrono::Duration::minutes(10);
        db.execute(
            "INSERT INTO focus_intervals VALUES('interval','run',1,?,?,?)",
            params![start.to_rfc3339(), end.to_rfc3339(), 600.0],
        )
        .unwrap();
        let days = stats(&db).unwrap();
        assert!((days[5].focus_seconds - 300.0).abs() < 0.01);
        assert!((days[6].focus_seconds - 300.0).abs() < 0.01);
    }
    #[test]
    fn legacy_string_preferences_are_preserved() {
        let db = Connection::open_in_memory().unwrap();
        db.execute_batch(include_str!("schema.sql")).unwrap();
        db.execute("INSERT INTO settings VALUES('study','\"50\"')", [])
            .unwrap();
        db.execute("INSERT INTO settings VALUES('break','\"10\"')", [])
            .unwrap();
        db.execute("INSERT INTO settings VALUES('final_break','true')", [])
            .unwrap();
        let prefs = preferences(&db).unwrap();
        assert_eq!(prefs.focus_minutes, 50);
        assert_eq!(prefs.break_minutes, 10);
        assert!(prefs.final_break);
        assert!(!prefs.notifications);
    }
}
