export interface Plan {
  title: string;
  focus_minutes: number;
  break_minutes: number;
  sessions: number;
  final_break: boolean;
}
export interface Task extends Plan {
  id: number;
  planned_date: string;
  priority: number;
  completed: boolean;
  completed_rounds: number;
}
export interface TaskInput extends Plan {
  id: number | null;
  planned_date: string;
  priority: number;
}
export interface Timer extends Plan {
  run_id: string;
  task_id: number | null;
  phase: "focus" | "break";
  session_index: number;
  remaining: number;
  paused: boolean;
  skipped: boolean;
  started_at: string;
}
export interface Preferences {
  focus_minutes: number;
  break_minutes: number;
  sessions: number;
  final_break: boolean;
  notifications: boolean;
  sound: boolean;
}
export interface DayStats {
  date: string;
  focus_seconds: number;
  sessions: number;
  tasks: number;
}
export interface History {
  id: string;
  title: string;
  status: string;
  started_at: string;
  focus_seconds: number;
  completed_sessions: number;
  sessions: number;
}
export interface Snapshot {
  tasks: Task[];
  timer: Timer | null;
  stats: DayStats[];
  history: History[];
  preferences: Preferences;
  database_path: string;
  today: string;
}
