import sqlite3
from datetime import date, datetime, timedelta, timezone

import flet as ft
import ui_theme as ui
import asyncio


def group_tasks_by_date(tasks, local_timezone=None):
    """SQLite CURRENT_TIMESTAMP is UTC; group by the user's local calendar day."""
    groups = {}
    for task in tasks:
        try:
            if task.get('planned_date'):
                day = date.fromisoformat(task['planned_date'])
                groups.setdefault(day, []).append(task)
                continue
            created = datetime.fromisoformat(task["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            day = created.astimezone(local_timezone).date()
        except (ValueError, TypeError, KeyError):
            day = None
        groups.setdefault(day, []).append(task)
    return [(day, sorted(groups[day], key=lambda task: (task["completed"], -task.get('priority', 1), -task["id"])))
            for day in sorted(groups, key=lambda value: value or date.min, reverse=True)]


class TaskList:
    def __init__(self, page, store, on_start):
        self.page, self.store, self.on_start = page, store, on_start
        self.rows = ft.Column(spacing=12)
        self.summary = ft.Text(color=ui.MUTED, size=14)
        self.expanded_dates = {}
        self.group_day = date.today()
        self.search_generation = 0
        self.search = ft.TextField(label='Search tasks', prefix_icon=ft.Icons.SEARCH_ROUNDED, expand=True, on_change=self.search_changed)
        self.status = ft.Dropdown(label='Status', value='all', width=155,
            options=[ft.dropdown.Option('all', 'All'), ft.dropdown.Option('pending', 'To do'), ft.dropdown.Option('completed', 'Completed')], on_change=lambda e: self.apply_filters())
        self.priority = ft.Dropdown(label='Priority', value='all', width=145,
            options=[ft.dropdown.Option('all', 'All'), ft.dropdown.Option('2', 'High'), ft.dropdown.Option('1', 'Normal'), ft.dropdown.Option('0', 'Low')], on_change=lambda e: self.apply_filters())
        self.date_filter = ft.TextField(label='Planned date', hint_text='YYYY-MM-DD', width=170, on_submit=lambda e: self.apply_filters())

    async def search_changed(self, e):
        self.search_generation += 1
        generation = self.search_generation
        await asyncio.sleep(.2)
        if generation == self.search_generation:
            self.apply_filters()

    def apply_filters(self):
        self.refresh()
        self.page.update()

    def clear_filters(self, e=None):
        self.search.value, self.status.value, self.priority.value, self.date_filter.value = '', 'all', 'all', ''
        self.apply_filters()

    def show_error(self, message):
        self.page.open(ft.SnackBar(content=ft.Text(message)))

    def edit(self, task=None):
        task = task or {}
        title = ft.TextField(label="Task name", value=task.get("title", ""), max_length=160, autofocus=True)
        focus = ft.TextField(label="Focus (min)", value=str(task.get("focus_minutes", 25)), width=144, keyboard_type=ft.KeyboardType.NUMBER)
        breaks = ft.TextField(label="Break (min)", value=str(task.get("break_minutes", 5)), width=144, keyboard_type=ft.KeyboardType.NUMBER)
        sessions = ft.TextField(label="Sessions", value=str(task.get("sessions", 4)), width=144, keyboard_type=ft.KeyboardType.NUMBER)
        planned = ft.TextField(label='Planned date', value=task.get('planned_date') or date.today().isoformat(), expand=True)
        def pick_date(e):
            def selected(event):
                planned.value = picker.value.date().isoformat()
                self.page.update()
            try:
                initial = date.fromisoformat(planned.value)
            except ValueError:
                initial = date.today()
            picker = ft.DatePicker(value=initial, current_date=date.today(), last_date=date(2100,12,31), on_change=selected)
            self.page.open(picker)
        priority = ft.Dropdown(label='Priority', value=str(task.get('priority', 1)), width=150,
            options=[ft.dropdown.Option('2', 'High'), ft.dropdown.Option('1', 'Normal'), ft.dropdown.Option('0', 'Low')])
        final_break = ft.Checkbox(label='Take a break after the final session', value=bool(task.get('final_break', True)))
        error = ft.Text(color=ui.DANGER, size=13)

        def save(e):
            try:
                self.store.save(title.value, focus.value, breaks.value, sessions.value, task.get("id"),
                    planned_date=planned.value, priority=int(priority.value), final_break=final_break.value)
            except ValueError as exc:
                error.value = str(exc)
                self.page.update()
                return
            except sqlite3.Error:
                error.value = "Could not save this task. Please try again."
                self.page.update()
                return
            self.page.close(dialog)
            self.refresh()
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Edit task" if task else "New task"),
            content=ft.Column([title, ft.Row([focus, breaks, sessions], wrap=True),
                ft.Row([planned, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH_OUTLINED, tooltip='Choose planned date', on_click=pick_date), priority]), final_break, error], width=500, tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)), ft.FilledButton("Save task", on_click=save)],
        )
        self.page.open(dialog)

    def toggle(self, task_id, value):
        try:
            self.store.set_completed(task_id, value)
            self.refresh()
            self.page.update()
        except (sqlite3.Error, ValueError):
            self.show_error("Could not update this task. Please try again.")

    def delete(self, task_id):
        try:
            self.store.delete(task_id)
        except (sqlite3.Error, ValueError):
            self.show_error("Could not delete this task. Please try again.")
            return
        self.refresh()
        self.page.update()
        self.page.open(ft.SnackBar(content=ft.Text("Task deleted"), action="Undo", duration=6000,
            on_action=lambda e: self.restore(task_id)))

    def restore(self, task_id):
        try:
            self.store.restore(task_id)
            self.refresh()
            self.page.update()
        except (sqlite3.Error, ValueError):
            self.show_error("Could not restore this task. Please try again.")

    def remember_expansion(self, day, expanded):
        self.expanded_dates[day] = str(expanded).lower() == "true"

    def move_today(self, task):
        try:
            self.store.save(task['title'], task['focus_minutes'], task['break_minutes'], task['sessions'], task['id'],
                planned_date=date.today().isoformat(), priority=task['priority'], final_break=task['final_break'])
            self.apply_filters()
        except (sqlite3.Error, ValueError):
            self.show_error('Could not reschedule this task.')

    def history(self, task):
        try:
            runs = self.store.history(task['id'])
        except sqlite3.Error:
            self.show_error('Could not load task history.')
            return
        rows = [ft.Text('No recorded focus yet. Start this task to build your history.', color=ui.MUTED)]
        if runs:
            rows = [ft.Container(padding=12, content=ft.Column([
                ft.Text(f"{datetime.fromisoformat(run['started_at']).astimezone():%d %b %Y, %H:%M} · {run['status'].title()}"),
                ft.Text(f"{run['focus_seconds']/60:.1f} min focused · {run['completed_sessions']} of {run['sessions']} sessions completed", color=ui.MUTED, size=12)
            ])) for run in runs]
        dialog = ft.AlertDialog(title=ft.Text(f"History · {task['title']}"), content=ft.Column(rows, width=520, height=320, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton('Close', on_click=lambda e: self.page.close(dialog))])
        self.page.open(dialog)

    def refresh(self):
        try:
            if self.date_filter.value:
                date.fromisoformat(self.date_filter.value)
            tasks = self.store.list_tasks(search=self.search.value or '', status=self.status.value,
                priority=None if self.priority.value == 'all' else int(self.priority.value), planned_date=self.date_filter.value or None)
        except ValueError:
            self.date_filter.error_text = 'Use YYYY-MM-DD'
            return
        except sqlite3.Error:
            self.rows.controls = [ft.Text("Could not load tasks. Reopen this tab to retry.", color=ui.DANGER)]
            return
        self.date_filter.error_text = None
        pending = sum(not task["completed"] for task in tasks)
        self.summary.value = f"{pending} to do · {len(tasks) - pending} completed"
        self.rows.controls = []
        today = date.today()
        if self.group_day != today:
            self.expanded_dates.clear()
            self.group_day = today
        for day, dated_tasks in group_tasks_by_date(tasks):
            label = "Today" if day == today else "Tomorrow" if day == today + timedelta(days=1) else "Yesterday" if day == today - timedelta(days=1) else day.strftime("%d %B %Y") if day else "Unknown date"
            count = sum(not task["completed"] for task in dated_tasks)
            self.rows.controls.append(ft.ExpansionTile(
                key=f"task-date-{day}",
                title=ft.Text(label, size=17, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(f"{count} to do · {len(dated_tasks)} tasks" + (f" · {day:%d %b %Y}" if day and label in ("Today", "Yesterday") else ""), size=12),
                leading=ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, color=ui.ACCENT),
                initially_expanded=self.expanded_dates.get(day, day == today),
                on_change=lambda e, d=day: self.remember_expansion(d, e.data),
                controls=[self.task_card(task) for task in dated_tasks],
                controls_padding=ft.padding.only(top=8, bottom=12),
                icon_color=ui.ACCENT, collapsed_icon_color=ui.MUTED,
                text_color=ui.TEXT, collapsed_text_color=ui.SECONDARY,
            ))
        if not tasks:
            self.rows.controls = [ft.Container(padding=28, bgcolor=ui.CARD, border_radius=16,
                content=ft.Column([ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=38, color=ui.ACCENT),
                    ft.Text("No matching tasks" if (self.search.value or self.status.value != 'all' or self.priority.value != 'all' or self.date_filter.value) else "Make room for your next goal", size=18, color=ui.TEXT),
                    ft.Text("Add a task or clear the filters to see more.", color=ui.MUTED)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER))]

    def task_card(self, task):
        completed = bool(task["completed"])
        return ft.Container(
            padding=12, margin=ft.margin.only(bottom=8), bgcolor=ui.CARD, border_radius=16, border=ft.border.all(1, ui.BORDER),
            content=ft.Row([
                ft.Checkbox(value=completed, tooltip="Mark incomplete" if completed else "Mark complete",
                    on_change=lambda e, task_id=task["id"]: self.toggle(task_id, e.control.value)),
                ft.Column([
                    ft.Text(task["title"], size=16, weight=ft.FontWeight.W_600, color=ui.MUTED if completed else ui.TEXT),
                    ft.Text(f'{task["focus_minutes"]} min focus · {task["break_minutes"]} min break · {task["sessions"]} sessions', size=12, color=ui.MUTED),
                    ft.Text(f"Last run: {task.get('completed_rounds',0)} of {task.get('last_run_sessions') or task['sessions']} focus sessions completed", size=11, color=ui.MUTED, visible=task.get('last_run_sessions') is not None),
                    ft.Row([ft.Text(['Low', 'Normal', 'High'][task.get('priority', 1)] + ' priority', size=11, color=[ui.MUTED,ui.ACCENT_TEXT,ui.WARNING][task.get('priority',1)]),
                        ft.Text('Overdue', color=ui.DANGER, size=11, visible=not completed and bool(task.get('planned_date')) and task.get('planned_date','') < date.today().isoformat())], spacing=12),
                ], spacing=5, expand=True),
                ft.IconButton(icon=ft.Icons.TODAY_OUTLINED, tooltip='Move to today', visible=not completed and bool(task.get('planned_date')) and task.get('planned_date','') < date.today().isoformat(), on_click=lambda e: self.move_today(task)),
                ft.IconButton(icon=ft.Icons.HISTORY_ROUNDED, tooltip='Task history', on_click=lambda e: self.history(task)),
                ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Edit task", on_click=lambda e, t=task: self.edit(t)),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=ui.DANGER, tooltip="Delete task",
                    on_click=lambda e, task_id=task["id"]: self.delete(task_id)),
                ft.FilledButton("Start", icon=ft.Icons.PLAY_ARROW_ROUNDED, disabled=completed,
                    on_click=lambda e, t=task: self.on_start(t)),
            ]),
        )

    def content(self):
        self.refresh()
        return ft.Container(width=720, padding=ft.padding.symmetric(horizontal=34, vertical=24), content=ft.Column([
            ft.Row([ft.Column([ft.Text("Your to-do list", size=30, weight=ft.FontWeight.W_700, color=ui.TEXT), self.summary], spacing=6, expand=True),
                ft.FilledButton("Add task", icon=ft.Icons.ADD_ROUNDED, on_click=lambda e: self.edit())]),
            ft.Text("A focus plan for every task. Finish all sessions to complete it automatically.", size=13, color=ui.MUTED),
            ft.Row([self.search, self.status]),
            ft.Row([self.priority, self.date_filter, ft.TextButton('Clear filters', on_click=self.clear_filters)], wrap=True),
            ft.Container(height=8), self.rows,
        ], spacing=12))
