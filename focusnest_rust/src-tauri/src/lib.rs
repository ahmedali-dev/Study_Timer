mod model;
mod runtime;
mod store;

use model::*;
use runtime::{Runtime, Snapshot};
use std::sync::Mutex;
use tauri::{Emitter, Manager, State};
use tauri_plugin_notification::NotificationExt;

struct AppState(Mutex<Runtime>);
fn locked(state: &AppState) -> AppResult<std::sync::MutexGuard<'_, Runtime>> {
    state
        .0
        .lock()
        .map_err(|_| "Application state lock failed. Restart FocusNest.".into())
}
#[tauri::command]
fn snapshot(state: State<'_, AppState>) -> AppResult<Snapshot> {
    locked(&state)?.snapshot()
}
#[tauri::command]
fn save_task(state: State<'_, AppState>, input: TaskInput) -> AppResult<()> {
    store::save_task(&locked(&state)?.db, input)
}
#[tauri::command]
fn complete_task(state: State<'_, AppState>, id: i64, completed: bool) -> AppResult<()> {
    let mut r = locked(&state)?;
    let tx = r.db.transaction().map_err(|e| e.to_string())?;
    store::complete(&tx, id, completed)?;
    tx.commit().map_err(|e| e.to_string())
}
#[tauri::command]
fn delete_task(state: State<'_, AppState>, id: i64, restore: bool) -> AppResult<()> {
    let r = locked(&state)?;
    let n =
        r.db.execute(
            if restore {
                "UPDATE tasks SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL"
            } else {
                "UPDATE tasks SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL"
            },
            [id],
        )
        .map_err(|e| e.to_string())?;
    if n == 0 {
        return Err("Task no longer exists.".into());
    }
    Ok(())
}
#[tauri::command]
fn start_timer(state: State<'_, AppState>, plan: Plan, task_id: Option<i64>) -> AppResult<()> {
    locked(&state)?.start(plan, task_id)
}
#[tauri::command]
fn timer_action(state: State<'_, AppState>, action: String) -> AppResult<()> {
    locked(&state)?.action(&action)
}
#[tauri::command]
fn save_preferences(state: State<'_, AppState>, preferences: Preferences) -> AppResult<()> {
    Plan {
        title: "Defaults".into(),
        focus_minutes: preferences.focus_minutes,
        break_minutes: preferences.break_minutes,
        sessions: preferences.sessions,
        final_break: preferences.final_break,
    }
    .validate()?;
    locked(&state)?
        .db
        .execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('rust_preferences',?)",
            [serde_json::to_string(&preferences).map_err(|e| e.to_string())?],
        )
        .map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
fn import_legacy(state: State<'_, AppState>, path: String) -> AppResult<()> {
    locked(&state)?.import_legacy(std::path::Path::new(&path))
}
#[tauri::command]
fn legacy_paths() -> Vec<String> {
    let mut paths = Vec::new();
    if cfg!(debug_assertions) {
        paths.push(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../data/study_timer.sqlite3"),
        );
    }
    if let Ok(home) = std::env::var(if cfg!(windows) { "USERPROFILE" } else { "HOME" }) {
        let base = if cfg!(target_os = "macos") {
            std::path::PathBuf::from(home).join("Library/Application Support")
        } else if cfg!(windows) {
            std::env::var_os("LOCALAPPDATA")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|| std::path::PathBuf::from(home).join("AppData/Local"))
        } else {
            std::env::var_os("XDG_DATA_HOME")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|| std::path::PathBuf::from(home).join(".local/share"))
        };
        paths.push(base.join("StudyTimer/study_timer.sqlite3"));
    }
    paths
        .into_iter()
        .filter(|p| p.is_file())
        .map(|p| p.canonicalize().unwrap_or(p).display().to_string())
        .collect()
}
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            let dir = std::env::var_os("FOCUSNEST_RUST_DATA_DIR")
                .map(std::path::PathBuf::from)
                .unwrap_or(app.path().app_data_dir()?);
            std::fs::create_dir_all(&dir)?;
            let runtime =
                Runtime::open(dir.join("focusnest.sqlite3")).map_err(std::io::Error::other)?;
            app.manage(AppState(Mutex::new(runtime)));
            let handle = app.handle().clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(std::time::Duration::from_secs(1));
                let state = handle.state::<AppState>();
                let Ok(mut r) = state.0.lock() else {
                    break;
                };
                let update = match r.tick() {
                    Ok(update) => update,
                    Err(error) => {
                        if let Some(t) = r.timer.as_mut() {
                            t.paused = true;
                        }
                        let _ = handle.emit("backend-error", format!("Timer paused: {error}"));
                        let _ = handle.emit("timer-tick", &r.timer);
                        continue;
                    }
                };
                let _ = handle.emit("timer-tick", &r.timer);
                if update.changed {
                    let _ = handle.emit("data-changed", ());
                }
                if let Some(message) = update.message {
                    let _ = handle.emit("session-event", &message);
                    if store::preferences(&r.db)
                        .map(|p| p.notifications)
                        .unwrap_or(false)
                    {
                        if let Err(error) = handle
                            .notification()
                            .builder()
                            .title("FocusNest")
                            .body(message)
                            .show()
                        {
                            let _ = handle.emit(
                                "backend-error",
                                format!("Notification unavailable: {error}"),
                            );
                        }
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            snapshot,
            save_task,
            complete_task,
            delete_task,
            start_timer,
            timer_action,
            save_preferences,
            import_legacy,
            legacy_paths
        ])
        .build(tauri::generate_context!())
        .expect("Could not initialize FocusNest");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state = handle.state::<AppState>();
            if let Ok(mut r) = state.0.lock() {
                if let Err(e) = r.action("pause") {
                    eprintln!("Could not checkpoint timer: {e}");
                }
            };
        }
    });
}
