import atexit
from datetime import date
import logging
import math
import os
import sqlite3
import sys
import threading

import flet as ft
import ui_theme as ui
import pygame

from TimerDisplay import TimerDisplay
from TimerForm import TimerForm
from TimerSettings import TimerSettings
from notifications import DesktopNotifications
from task_store import TaskStore
from timer_controller import TimerController, InstanceLock
from TaskList import TaskList
from ProgressView import ProgressView
import timerModel
from branding import APP_NAME, VERSION, ICON_PNG, ICON_ICO


def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def getPath(path):
    return resource_path(path)


def main(page: ft.Page):
    page.title = APP_NAME
    page.window.icon = getPath('assets/' + ICON_ICO)
    page.window.width, page.window.height = 1080, 850
    page.window.min_width, page.window.min_height = 820, 640
    page.window.center()
    page.padding = 0
    page.bgcolor = ui.BACKGROUND
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ui.ACCENT)
    instance = None
    try:
        task_store = TaskStore()
        instance = InstanceLock(task_store.path)
        data = timerModel.loadData(task_store)
    except (OSError, ValueError, sqlite3.Error) as exc:
        if instance:
            instance.close()
        page.add(ft.Text(str(exc), color=ui.DANGER))
        return
    notifications = DesktopNotifications(getPath('assets/' + ICON_ICO))
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    def audio_stop():
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.stop()

    def play_audio(path, volume=.3, loops=0):
        if not path or not os.path.isfile(path) or not pygame.mixer.get_init():
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=loops)
        except (pygame.error, OSError):
            pass

    def error(message):
        page.open(ft.SnackBar(content=ft.Text(message), duration=7000))

    def safe(action):
        try:
            action()
        except (ValueError, TypeError, sqlite3.Error, OSError) as exc:
            with controller.lock:
                if controller.state:
                    controller.state['paused'] = True
            audio_stop()
            error(f'Could not save timer progress: {exc}. Please try again.')

    timer_display = TimerDisplay(page)
    timer_form = TimerForm(page, data)
    area = ft.Container(expand=True, alignment=ft.alignment.top_center)
    sidebar = ft.Container(bgcolor=ui.SIDEBAR, border=ft.border.only(right=ft.BorderSide(1, ui.BORDER)))
    sidebar_status = ft.Text('', size=11, color=ui.ACCENT_TEXT, visible=False)
    active_tab = 'timer'
    showing_timer = False
    shutting_down = threading.Event()
    last_display = None
    last_day = date.today()
    refresh_counter = 0

    def test_notification(e):
        def result(success, message):
            timer_settings.notificationStatus.value = message
            page.update()
        notifications.send(APP_NAME, 'Notifications are ready. Time to focus!', on_result=result)

    timer_settings = TimerSettings(page, [None, None, data.get('bg_music', '')], test_notification, store=task_store)
    task_list = TaskList(page, task_store, on_start=lambda task: start_timer(task))
    progress = ProgressView(task_store)

    def refresh_sidebar():
        compact = (page.width or page.window.width or 1080) < 980
        sidebar_status.visible = controller.snapshot() is not None
        sidebar.width = 76 if compact else 208
        navigation = []
        for name, label, icon in [('timer', 'Timer', ft.Icons.TIMER_OUTLINED), ('tasks', 'To-do list', ft.Icons.CHECKLIST_ROUNDED), ('progress', 'Progress', ft.Icons.INSIGHTS_ROUNDED)]:
            selected = active_tab == name
            navigation.append(ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=14), border_radius=12,
                bgcolor=ui.SELECTED if selected else None, tooltip=label, on_click=lambda e, tab=name: select_tab(tab),
                content=ft.Row([ft.Icon(icon, size=22, color=ui.ACCENT_TEXT if selected else ui.MUTED),
                    ft.Text(label, size=14, weight=ft.FontWeight.W_600, color=ui.TEXT if selected else ui.MUTED, visible=not compact)], spacing=12)))
        sidebar.content = ft.Column([
            ft.Container(padding=ft.padding.symmetric(horizontal=12, vertical=22),
                content=ft.Row([ft.Image(src=ICON_PNG, width=32, height=32, fit=ft.ImageFit.CONTAIN),
                    ft.Text(APP_NAME, size=17, weight=ft.FontWeight.W_700, visible=not compact)], spacing=10)),
            *navigation,
            ft.Container(content=sidebar_status, padding=12, visible=not compact),
            ft.Container(expand=True),
            ft.Container(padding=14, border_radius=12, tooltip='Sound & notifications',
                on_click=lambda e: page.open(timer_settings.dlg),
                content=ft.Row([ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=22, color=ui.MUTED),
                    ft.Text('Settings', color=ui.MUTED, visible=not compact)], spacing=12)),
            ft.Container(padding=ft.padding.only(left=14, bottom=20), visible=not compact,
                content=ft.Text(f'v{VERSION} · Saved locally', color=ui.MUTED, size=11)),
        ], expand=True, spacing=8)
        sidebar.padding = ft.padding.symmetric(horizontal=10)

    def home_content():
        body = task_list.content() if active_tab == 'tasks' else progress.content() if active_tab == 'progress' else timer_form.content()
        return ft.Column([
            ft.Container(height=16), body,
        ], expand=True, alignment=ft.MainAxisAlignment.START, horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)

    def show_home():
        nonlocal showing_timer
        showing_timer = False
        area.content = home_content()
        refresh_sidebar()
        page.update()

    def select_tab(tab):
        nonlocal active_tab
        active_tab = tab
        safe(show_timer if tab == 'timer' and controller.snapshot() else show_home)

    def show_timer():
        nonlocal showing_timer, last_display, active_tab
        active_tab = 'timer'
        showing_timer, last_display = True, None
        area.content = ft.Column([ft.Container(height=24), timer_display.content()], expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)
        refresh_sidebar()
        render_timer()

    def render_timer():
        nonlocal last_display
        state = controller.snapshot()
        if state is None:
            sidebar_status.visible = False
            if showing_timer:
                show_home()
            return
        seconds = math.ceil(state['remaining'])
        sidebar_status.visible = True
        sidebar_status.value = f"{'Paused' if state['paused'] else state['phase'].title()} · {seconds//60:02d}:{seconds%60:02d}"
        display_key = (seconds, state['phase'], state['session_index'], state['paused'])
        if display_key == last_display:
            return
        last_display = display_key
        duration = (state['focus_minutes'] if state['phase'] == 'focus' else state['break_minutes']) * 60
        timer_display.timer_display.value = f'{seconds // 60:02d}:{seconds % 60:02d}'
        timer_display.session.value = f"{state['phase'].title()} · {state['session_index']} of {state['sessions']}"
        timer_display.task_title.value = state['title']
        timer_display.progress.value = 1 - state['remaining'] / duration if duration else 1
        timer_display.state_label.value = 'Paused · saved' if state['paused'] else 'In progress'
        timer_display.btnPause.text = 'Resume' if state['paused'] else 'Pause'
        timer_display.btnPause.icon = ft.Icons.PLAY_ARROW_ROUNDED if state['paused'] else ft.Icons.PAUSE_ROUNDED
        timer_display.btnSkip.text = 'Skip break' if state['phase'] == 'break' else 'Next session'
        page.update()

    def on_event(event, state):
        if shutting_down.is_set():
            return
        if event in ('completed', 'skipped', 'interrupted'):
            audio_stop()
            if event == 'completed':
                notifications.send('All sessions complete', f"{state['title']} · {state['sessions']} focus sessions completed.")
            if not showing_timer:
                show_home()
        elif event == 'suspended':
            audio_stop()
            error('Timer paused after a system interruption. Resume when you are ready.')
        elif event in ('focus', 'break', 'resume'):
            if event == 'resume':
                if pygame.mixer.get_init():
                    pygame.mixer.unpause()
                    pygame.mixer.music.unpause()
                    if state['phase'] == 'focus' and pygame.mixer.music.get_pos() < 0:
                        play_audio(timer_settings.bgMusic.value, loops=-1)
                return
            audio_stop()
            if not state['paused']:
                if state['phase'] == 'focus':
                    play_audio(timer_settings.bgMusic.value, loops=-1)
                    if pygame.mixer.get_init():
                        try:
                            pygame.mixer.Sound(getPath('assets/start_sound.mp3')).play()
                        except (pygame.error, OSError):
                            pass
                else:
                    play_audio(getPath('assets/finish_sound.mp3'), volume=1)
            if event != 'resume':
                notifications.send('Time to focus' if event == 'focus' else 'Take a break', f"{state['title']} · session {state['session_index']} of {state['sessions']}")

    controller = TimerController(task_store, on_change=render_timer, on_event=on_event)

    def start_timer(task=None):
        if controller.snapshot() is not None:
            select_tab('timer')
            error('A session is already in progress. End it before starting another task.')
            return
        def start():
            if task is not None:
                current = task_store.get(task['id'])
                if not current or current['completed']:
                    show_home()
                    return
                controller.start(current['title'], current['focus_minutes'], current['break_minutes'], current['sessions'], current['id'], bool(current['final_break']))
            else:
                _, study, breaks, sessions = task_store.validate('Focus session', timer_form.timerMinutes.value, timer_form.timerBreak.value, timer_form.timerSessions.value)
                task_store.save_settings(dict(study=str(study), **{'break': str(breaks)}, session=str(sessions), final_break=timer_form.finalBreak.value))
                controller.start('Focus session', study, breaks, sessions, final_break=timer_form.finalBreak.value)
            show_timer()
        safe(start)

    def pause_resume(e):
        def change():
            state = controller.snapshot()
            if state and state['paused']:
                controller.resume()
            elif state:
                controller.pause()
                if pygame.mixer.get_init():
                    pygame.mixer.music.pause()
                    pygame.mixer.pause()
        safe(change)

    def skip(e):
        state = controller.snapshot()
        if not state:
            return
        if state['phase'] == 'break':
            safe(controller.skip)
            return
        def confirm(e):
            page.close(dialog)
            current = controller.snapshot()
            if current and (current['run_id'], current['phase'], current['session_index']) == (state['run_id'], state['phase'], state['session_index']):
                safe(controller.skip)
        dialog = ft.AlertDialog(modal=True, title=ft.Text('Skip this focus session?'),
            content=ft.Text('Time already focused is saved. This round will be recorded as skipped, not completed.'),
            actions=[ft.TextButton('Keep focusing', on_click=lambda e: page.close(dialog)), ft.FilledButton('Next session', on_click=confirm)])
        page.open(dialog)

    timer_form.startTimer.on_click = lambda e: start_timer()
    timer_form.settings.on_click = lambda e: page.open(timer_settings.dlg)
    timer_display.btnPause.on_click = pause_resume
    timer_display.btnStop.on_click = lambda e: safe(controller.stop)
    timer_display.btnSkip.on_click = skip

    def cleanup():
        if shutting_down.is_set():
            return
        controller.on_change = lambda: None
        controller.on_event = lambda event, state: None
        controller.suspend()
        shutting_down.set()
        audio_stop()
        instance.close()

    async def window_event(e):
        if e.data == 'close':
            try:
                cleanup()
            except (OSError, sqlite3.Error) as exc:
                error(f'Could not save progress before closing: {exc}. Try again.')
                controller.on_change, controller.on_event = render_timer, on_event
                return
            page.window.on_event = None
            page.on_disconnect = None
            page.window.destroy()
        elif e.data == 'focus' and not controller.snapshot():
            safe(show_home)

    page.window.prevent_close = True
    page.window.on_event = window_event
    async def disconnected(e):
        try:
            cleanup()
        except (OSError, sqlite3.Error):
            logging.exception('Could not checkpoint a disconnected timer')
    page.on_disconnect = disconnected
    atexit.register(cleanup)
    def resized(e):
        refresh_sidebar()
        page.update()
    page.on_resized = resized
    page.add(ft.Row([sidebar, area], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH))
    show_home()
    try:
        recovered = controller.recover()
    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        recovered = False
        def discard_invalid(e):
            def discard():
                task_store.discard_invalid_checkpoint()
                controller.state = None
                page.close(invalid_recovery)
                show_home()
            safe(discard)
        invalid_recovery = ft.AlertDialog(modal=True, title=ft.Text('Saved timer needs attention'),
            content=ft.Text(f'{exc}\nYour tasks and history are preserved. You can discard only the unfinished timer.'),
            actions=[ft.TextButton('Keep saved timer', on_click=lambda e: page.close(invalid_recovery)),
                     ft.FilledButton('Discard saved timer', on_click=discard_invalid)])
        page.open(invalid_recovery)
    if recovered:
        state = controller.snapshot()
        def resume_saved(e):
            page.close(recovery)
            show_timer()  # Intentionally paused until Resume is pressed.
        def discard_saved(e):
            page.close(recovery)
            safe(controller.stop)
            show_home()
        seconds = math.ceil(state['remaining'])
        recovery = ft.AlertDialog(modal=True, title=ft.Text('Continue your saved session?'),
            content=ft.Text(f"{state['title']}\n{state['phase'].title()} · session {state['session_index']} of {state['sessions']}\n{seconds//60:02d}:{seconds%60:02d} remaining. Restores paused."),
            actions=[ft.TextButton('Discard session', on_click=discard_saved), ft.FilledButton('Resume session', on_click=resume_saved)])
        page.open(recovery)

    def worker():
        nonlocal refresh_counter, last_day
        while not shutting_down.wait(.2):
            try:
                controller.tick()
                refresh_counter += 1
                if not showing_timer and (date.today() != last_day or (active_tab == 'progress' and refresh_counter % 150 == 0)):
                    last_day = date.today()
                    show_home()
            except (sqlite3.Error, OSError, ValueError) as exc:
                with controller.lock:
                    if controller.state:
                        controller.state['paused'] = True
                audio_stop()
                logging.exception('Timer checkpoint failed')
                error(f'Timer paused because progress could not be saved: {exc}')
    threading.Thread(target=worker, daemon=True, name='focus-timer').start()


if __name__ == '__main__':
    from desktop_runtime import prepare_desktop_runtime
    prepare_desktop_runtime()
    ft.app(target=main, assets_dir=resource_path('assets'))
