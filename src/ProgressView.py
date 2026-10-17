from datetime import date, datetime

import flet as ft
import ui_theme as ui
import sqlite3


class ProgressView:
    def __init__(self, store):
        self.store = store
        self.selected_day = None

    def content(self):
        stats = self.store.daily_stats()
        today = stats[date.today().isoformat()]
        cards = []
        for value, label in ((f"{today['focus_seconds']/60:.1f}", 'minutes focused'), (str(today['sessions']), 'sessions completed'), (str(today['tasks']), 'tasks completed')):
            cards.append(ft.Container(expand=True, padding=18, bgcolor=ui.SURFACE, border_radius=16,
                content=ft.Column([ft.Text(value, size=28, weight=ft.FontWeight.W_700, color=ui.ACCENT_TEXT), ft.Text(label, size=12, color=ui.MUTED)], spacing=4)))
        chart = []
        peak = max(60, max(item['focus_seconds'] for item in stats.values()))
        detail = ft.Column()
        history_panel = ft.Column(spacing=10)

        def history_rows(runs):
            return [ft.Container(padding=12, bgcolor=ui.CARD, border_radius=12,
                content=ft.Column([ft.Text(run['title'], weight=ft.FontWeight.W_600),
                    ft.Text(f"{datetime.fromisoformat(run['started_at']).astimezone():%d %b, %H:%M} · {run['focus_seconds']/60:.1f} min · {run['completed_sessions']}/{run['sessions']} sessions · {run['status']}", size=12, color=ui.MUTED)])) for run in runs[:30]] or [ft.Text('No recorded activity for this view yet.', color=ui.MUTED)]

        def inspect_day(day):
            self.selected_day = day
            item = stats[day]
            detail.controls = [ft.Text(f"{day} · {item['focus_seconds']/60:.1f} min · {item['sessions']} sessions · {item['tasks']} tasks", color=ui.SECONDARY)]
            try:
                history_panel.controls = history_rows(self.store.history_for_day(day))
            except sqlite3.Error:
                detail.controls = [ft.Text('Could not load activity for this day. Please try again.', color=ui.DANGER)]
            self.panel.update()

        for day, item in sorted(stats.items()):
            chart.append(ft.Container(expand=True, tooltip=f"{day}: {item['focus_seconds']/60:.1f} focused minutes", on_click=lambda e, d=day: inspect_day(d),
                content=ft.Column([
                    ft.Text(f"{item['focus_seconds']/60:.0f}m", size=11, color=ui.MUTED),
                    ft.Container(height=max(3, item['focus_seconds']/peak*120), width=32, bgcolor=ui.ACCENT, border_radius=7),
                    ft.Text(date.fromisoformat(day).strftime('%a'), size=12, color=ui.SECONDARY),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.END, height=165)))
        runs = self.store.history()
        history_panel.controls = history_rows(runs)
        self.panel = ft.Container(width=720, padding=ft.padding.symmetric(horizontal=34, vertical=24), content=ft.Column([
            ft.Text('Your progress', size=30, weight=ft.FontWeight.W_700),
            ft.Text('Today · actual work, including partial sessions', color=ui.MUTED),
            ft.Row(cards, spacing=12),
            ft.Container(height=8), ft.Text('Last 7 days', size=19, weight=ft.FontWeight.W_600),
            ft.Text('Local timezone · select a day to inspect it', size=12, color=ui.MUTED),
            ft.Row(chart, vertical_alignment=ft.CrossAxisAlignment.END), detail,
            ft.Text('Recent activity', size=19, weight=ft.FontWeight.W_600),
            history_panel,
        ], spacing=14))
        return self.panel
