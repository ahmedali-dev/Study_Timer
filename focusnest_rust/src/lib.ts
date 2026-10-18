export function localDate(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function clock(seconds: number): string {
  const value = Math.max(0, Math.ceil(Number.isFinite(seconds) ? seconds : 0));
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}
export function dateLabel(day: string, today: string): string {
  if (day === today) return "Today";
  const tomorrow = new Date(`${today}T12:00:00`);
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (day === localDate(tomorrow)) return "Tomorrow";
  return new Date(`${day}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
export function groupTasks<
  T extends {
    planned_date: string;
    title: string;
    completed: boolean;
    priority: number;
  },
>(
  tasks: T[],
  search: string,
  status: string,
  priority: string,
): [string, T[]][] {
  const groups = new Map<string, T[]>();
  for (const task of tasks) {
    if (
      !task.title
        .toLocaleLowerCase()
        .includes(search.trim().toLocaleLowerCase())
    )
      continue;
    if (
      (status === "pending" && task.completed) ||
      (status === "completed" && !task.completed)
    )
      continue;
    if (priority !== "all" && task.priority !== Number(priority)) continue;
    const group = groups.get(task.planned_date) ?? [];
    group.push(task);
    groups.set(task.planned_date, group);
  }
  return [...groups].sort(([a], [b]) => b.localeCompare(a));
}
