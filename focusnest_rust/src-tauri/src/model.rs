use chrono::{Local, NaiveDate};
use serde::{Deserialize, Serialize};

pub type AppResult<T> = Result<T, String>;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Plan {
    pub title: String,
    pub focus_minutes: i64,
    pub break_minutes: i64,
    pub sessions: i64,
    pub final_break: bool,
}
impl Plan {
    pub fn validate(&self) -> AppResult<()> {
        if self.title.trim().is_empty() || self.title.trim().chars().count() > 160 {
            return Err("Use a title between 1 and 160 characters.".into());
        }
        if !(1..=1440).contains(&self.focus_minutes)
            || !(0..=1440).contains(&self.break_minutes)
            || !(1..=1000).contains(&self.sessions)
        {
            return Err("Focus: 1–1440 minutes; break: 0–1440 minutes; sessions: 1–1000.".into());
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskInput {
    pub id: Option<i64>,
    #[serde(flatten)]
    pub plan: Plan,
    pub planned_date: String,
    pub priority: i64,
}
impl TaskInput {
    pub fn validate(&self) -> AppResult<()> {
        self.plan.validate()?;
        NaiveDate::parse_from_str(&self.planned_date, "%Y-%m-%d")
            .map_err(|_| "Choose a valid planned date.")?;
        if !(0..=2).contains(&self.priority) {
            return Err("Invalid priority.".into());
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Task {
    pub id: i64,
    pub title: String,
    pub focus_minutes: i64,
    pub break_minutes: i64,
    pub sessions: i64,
    pub final_break: bool,
    pub planned_date: String,
    pub priority: i64,
    pub completed: bool,
    pub completed_rounds: i64,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Timer {
    pub run_id: String,
    pub task_id: Option<i64>,
    pub title: String,
    pub focus_minutes: i64,
    pub break_minutes: i64,
    pub sessions: i64,
    pub final_break: bool,
    pub phase: String,
    pub session_index: i64,
    pub remaining: f64,
    pub paused: bool,
    pub skipped: bool,
    pub started_at: String,
}
impl Timer {
    pub fn validate(&self) -> AppResult<()> {
        if !["focus", "break"].contains(&self.phase.as_str())
            || self.focus_minutes <= 0
            || self.break_minutes < 0
            || self.sessions <= 0
            || self.session_index < 1
            || self.session_index > self.sessions
            || !self.remaining.is_finite()
            || self.remaining < 0.0
        {
            return Err("Invalid saved timer. The database was left unchanged.".into());
        }
        Ok(())
    }
    // One phase per tick. Delays never silently consume the next session.
    pub fn advance(&mut self, skip: bool) -> Transition {
        let session_result = if self.phase == "focus" {
            Some(if skip { "skipped" } else { "completed" })
        } else {
            None
        };
        if self.phase == "focus" {
            self.skipped |= skip;
            if !skip
                && self.break_minutes > 0
                && (self.session_index < self.sessions || self.final_break)
            {
                self.phase = "break".into();
                self.remaining = (self.break_minutes * 60) as f64;
            } else if self.session_index < self.sessions {
                self.session_index += 1;
                self.remaining = (self.focus_minutes * 60) as f64;
            } else {
                return Transition {
                    session_result,
                    outcome: Some(if self.skipped { "skipped" } else { "completed" }),
                };
            }
        } else if self.session_index < self.sessions {
            self.phase = "focus".into();
            self.session_index += 1;
            self.remaining = (self.focus_minutes * 60) as f64;
        } else {
            return Transition {
                session_result,
                outcome: Some(if self.skipped { "skipped" } else { "completed" }),
            };
        }
        Transition {
            session_result,
            outcome: None,
        }
    }
}
#[derive(Default)]
pub struct Transition {
    pub session_result: Option<&'static str>,
    pub outcome: Option<&'static str>,
}
#[derive(Clone, Serialize, Deserialize)]
pub struct Preferences {
    pub focus_minutes: i64,
    pub break_minutes: i64,
    pub sessions: i64,
    pub final_break: bool,
    pub notifications: bool,
    pub sound: bool,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            focus_minutes: 25,
            break_minutes: 5,
            sessions: 4,
            final_break: false,
            notifications: false,
            sound: true,
        }
    }
}
#[derive(Serialize, Default)]
pub struct DayStats {
    pub date: String,
    pub focus_seconds: f64,
    pub sessions: i64,
    pub tasks: i64,
}
#[derive(Serialize)]
pub struct History {
    pub id: String,
    pub title: String,
    pub status: String,
    pub started_at: String,
    pub focus_seconds: f64,
    pub completed_sessions: i64,
    pub sessions: i64,
}
pub fn today() -> String {
    Local::now().format("%Y-%m-%d").to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    fn timer() -> Timer {
        Timer {
            run_id: "test".into(),
            task_id: None,
            title: "Test".into(),
            focus_minutes: 1,
            break_minutes: 1,
            sessions: 2,
            final_break: false,
            phase: "focus".into(),
            session_index: 1,
            remaining: 0.0,
            paused: false,
            skipped: false,
            started_at: String::new(),
        }
    }
    #[test]
    fn focus_break_focus_complete() {
        let mut t = timer();
        assert_eq!(t.advance(false).session_result, Some("completed"));
        assert_eq!(t.phase, "break");
        t.advance(false);
        assert_eq!(t.session_index, 2);
        assert_eq!(t.phase, "focus");
        assert_eq!(t.advance(false).outcome, Some("completed"));
    }
    #[test]
    fn final_break_is_optional() {
        let mut t = timer();
        t.sessions = 1;
        t.final_break = true;
        assert!(t.advance(false).outcome.is_none());
        assert_eq!(t.phase, "break");
        assert_eq!(t.advance(false).outcome, Some("completed"));
    }
    #[test]
    fn skipped_focus_never_completes_task() {
        let mut t = timer();
        assert_eq!(t.advance(true).session_result, Some("skipped"));
        assert_eq!(t.phase, "focus");
        assert_eq!(t.session_index, 2);
        assert_eq!(t.advance(false).outcome, Some("skipped"));
    }
    #[test]
    fn skip_break_does_not_mark_focus_skipped() {
        let mut t = timer();
        t.advance(false);
        t.advance(true);
        assert!(!t.skipped);
        assert_eq!(t.advance(false).outcome, Some("completed"));
    }
    #[test]
    fn zero_break_advances_to_focus() {
        let mut t = timer();
        t.break_minutes = 0;
        t.advance(false);
        assert_eq!(t.phase, "focus");
        assert_eq!(t.session_index, 2);
    }
    #[test]
    fn invalid_recovery_is_rejected() {
        let mut t = timer();
        t.remaining = f64::NAN;
        assert!(t.validate().is_err());
    }
}
