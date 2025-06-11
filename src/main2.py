import flet as ft
import time
import threading


def main(page: ft.Page):
    page.title = "Study Timer App"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # Timer settings
    study_minutes = ft.TextField(label="Study (min)", value="50")
    break_minutes = ft.TextField(label="Break (min)", value="10")
    total_sessions = ft.TextField(label="Sessions", value="4")

    # Sound settings
    study_end_sound = ft.TextField(label="Study End Sound", value="study_end.wav")
    break_start_sound = ft.TextField(label="Break Start Sound", value="break_start.wav")
    bg_music_file = ft.TextField(label="Background Music", value="background.mp3")
    bg_music_volume = ft.Slider(min=0, max=100, divisions=100, value=20, label="{value}%")

    # Timer display
    timer_display = ft.Text("00:00", size=48, weight=ft.FontWeight.BOLD, color="green")
    session_info = ft.Text("")

    # Control buttons
    start_button = ft.ElevatedButton("Start", on_click=lambda _: start_timer())
    pause_button = ft.ElevatedButton("Pause", on_click=lambda _: pause_timer(), disabled=True)
    stop_button = ft.ElevatedButton("Stop", on_click=lambda _: stop_timer(), disabled=True)

    # Timer state
    running = False
    paused = False

    def update_timer_display(minutes, seconds):
        timer_display.value = f"{minutes:02}:{seconds:02}"
        page.update()

    def countdown(minutes):
        nonlocal running, paused
        total_seconds = minutes * 60
        while total_seconds > 0 and running:
            if not paused:
                mins, secs = divmod(total_seconds, 60)
                update_timer_display(mins, secs)
                time.sleep(1)
                total_seconds -= 1
        if running:
            update_timer_display(0, 0)

    def start_timer():
        nonlocal running, paused
        running = True
        paused = False
        start_button.disabled = True
        pause_button.disabled = False
        stop_button.disabled = False
        page.update()

        study_time = int(study_minutes.value)
        threading.Thread(target=countdown, args=(study_time,), daemon=True).start()

    def pause_timer():
        nonlocal paused
        paused = not paused
        pause_button.text = "Resume" if paused else "Pause"
        page.update()

    def stop_timer():
        nonlocal running, paused
        running = False
        paused = False
        start_button.disabled = False
        pause_button.disabled = True
        stop_button.disabled = True
        update_timer_display(0, 0)
        page.update()

    # Layout
    page.add(
        ft.Column([
            timer_display,
            ft.Row([start_button, pause_button, stop_button], alignment=ft.MainAxisAlignment.CENTER),
            session_info,
            ft.Divider(),
            ft.Text("Timer Settings", size=16, weight=ft.FontWeight.BOLD),
            study_minutes, break_minutes, total_sessions,
            ft.Text("Sound Settings", size=16, weight=ft.FontWeight.BOLD),
            study_end_sound, break_start_sound, bg_music_file, bg_music_volume,
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )


ft.app(target=main)
