import flet as ft
import ui_theme as ui
from branding import APP_NAME


class TimerForm:
    """Setup screen for a focus session."""

    def __init__(self, page, data=None):
        self.page = page
        data = data or {"study": 50, "break": 10, "session": 4}
        surface, border, accent = ui.SURFACE, ui.FIELD_BORDER, ui.ACCENT
        field = dict(border_color=border, focused_border_color=accent, cursor_color=accent,
                     text_style=ft.TextStyle(size=18), keyboard_type=ft.KeyboardType.NUMBER)
        self.timerMinutes = ft.TextField(label="Focus time", suffix_text="min", value=str(data.get("study", 50)), width=156, **field)
        self.timerBreak = ft.TextField(label="Break time", suffix_text="min", value=str(data.get("break", 10)), width=156, **field)
        self.timerSessions = ft.TextField(label="Sessions", suffix_text="rounds", value=str(data.get("session", 4)), width=156, **field)
        self.finalBreak = ft.Checkbox(label='Take a break after the final session', value=bool(data.get('final_break', True)))
        self.startTimer = ft.FilledButton("Start focus session", icon=ft.Icons.PLAY_ARROW_ROUNDED, height=48,
            style=ft.ButtonStyle(bgcolor=accent, color=ui.ON_ACCENT, shape=ft.RoundedRectangleBorder(radius=14), text_style=ft.TextStyle(weight=ft.FontWeight.W_600, size=15)))
        self.settings = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Sound & notification settings", icon_color=ui.SECONDARY, bgcolor=surface,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)))
        self.dlg = ft.AlertDialog(title=ft.Text("Check your settings"), content=ft.Text("Please enter a valid number for each timer field."),
            actions=[ft.TextButton("Close", on_click=lambda e: page.close(self.dlg))], actions_alignment=ft.MainAxisAlignment.END)

    def content(self) -> ft.Container:
        return ft.Container(width=720, padding=ft.padding.symmetric(horizontal=34, vertical=28), content=ft.Column([
            ft.Row([ft.Column([ft.Text(APP_NAME, size=30, weight=ft.FontWeight.W_700, color=ui.TEXT),
                ft.Text("Set up a focused session and make some progress.", size=14, color=ui.MUTED)], spacing=5, expand=True),
                ft.Container(content=ft.Row([ft.Icon(ft.Icons.WB_SUNNY_OUTLINED, size=17, color=ui.WARNING), ft.Text("Focus mode", size=12, color=ui.SECONDARY)], spacing=7), padding=ft.padding.symmetric(horizontal=13, vertical=9), bgcolor=ui.BADGE, border_radius=20)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=18),
            ft.Container(padding=ft.padding.all(22), bgcolor=ui.CARD, border_radius=20, border=ft.border.all(1, ui.BORDER), content=ft.Column([
                ft.Text("SESSION PLAN", size=11, weight=ft.FontWeight.W_700, color=ui.MUTED), ft.Container(height=11),
                ft.Row([self.timerMinutes, self.timerBreak, self.timerSessions], spacing=16), self.finalBreak])),
            ft.Container(height=18),
            ft.Row([ft.Column([ft.Text("Ready when you are", size=15, weight=ft.FontWeight.W_600, color=ui.TEXT), ft.Text("You can change sounds from settings.", size=12, color=ui.MUTED)], spacing=4, expand=True), self.startTimer, self.settings], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        ], spacing=0))

    def get_page(self): return self.page
    def get_timer_minutes(self): return self.timerMinutes
    def get_timer_break(self): return self.timerBreak
    def get_timer_sessions(self): return self.timerSessions
    def get_timer_start(self): return self.startTimer
    def get_timer_settings(self): return self.settings
