import flet as ft
import ui_theme as ui


class TimerDisplay:
    """Active-session screen."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.task_title = ft.Text("Stay present. One session at a time.", size=14, color=ui.MUTED)
        self.session = ft.Text("Focus session", size=15, weight=ft.FontWeight.W_600, color=ui.ACCENT_TEXT)
        self.timer_display = ft.Text("00:00", size=64, weight=ft.FontWeight.W_700, color=ui.TEXT)
        self.progress = ft.ProgressRing(value=0, width=248, height=248, stroke_width=8, color=ui.ACCENT, bgcolor=ui.RING_TRACK)
        self.btnPause = ft.FilledButton("Pause", icon=ft.Icons.PAUSE_ROUNDED, height=45)
        self.btnStop = ft.OutlinedButton("End session", icon=ft.Icons.STOP_ROUNDED, height=45)
        self.btnSkip = ft.TextButton('Next session', icon=ft.Icons.SKIP_NEXT_ROUNDED)
        self.state_label = ft.Text('In progress', size=12, color=ui.SECONDARY)

    def content(self) -> ft.Container:
        timer_face = ft.Stack([
            self.progress,
            ft.Container(content=ft.Column([self.session, self.timer_display], spacing=4, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER), width=248, height=248, alignment=ft.alignment.center),
        ], width=248, height=248)
        return ft.Container(width=720, padding=ft.padding.symmetric(horizontal=34, vertical=28), content=ft.Column([
            ft.Row([ft.Column([ft.Text("Deep work", size=30, weight=ft.FontWeight.W_700, color=ui.TEXT), self.task_title], spacing=5, expand=True),
                ft.Container(content=ft.Row([ft.Container(width=8, height=8, bgcolor=ui.SUCCESS, border_radius=8), self.state_label], spacing=8), padding=ft.padding.symmetric(horizontal=13, vertical=9), bgcolor=ui.SUCCESS_BG, border_radius=20)]),
            ft.Container(height=32), ft.Container(content=timer_face, alignment=ft.alignment.center), ft.Container(height=26),
            ft.Row([self.btnPause, self.btnStop], alignment=ft.MainAxisAlignment.CENTER, spacing=12), self.btnSkip
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0))

    def get_page(self): return self.page
    def get_session(self): return self.session
    def get_timer_display(self): return self.timer_display
    def get_btn_pause(self): return self.btnPause
    def get_btn_stop(self): return self.btnStop
