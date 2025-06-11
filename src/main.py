import flet as ft
from TimerDisplay import TimerDisplay
from TimerForm import TimerForm
from TimerSettings import TimerSettings
import timerModel
from LoaderAnimation import LoaderCircle
import time
import threading
import plyer.platforms.win.notification
from plyer import notification
import pygame
import os
import sys


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS  # PyInstaller temporary folder
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def getPath(p):
    settingsPath = os.path.join(os.path.dirname(__file__), p)
    # return settingsPath
    return resource_path(p)


def main(page: ft.Page):
    # page.window.title_bar_hidden = True
    page.title = "Study Timer"
    icon_path = getPath("assets/icon.ico")
    page.window.width = 800
    page.window.height = 500
    page.window.center()
    # page.set_ic
    data = timerModel.loadData()
    # def change_button(e):
    #     if e.state == ft.AudioState.PAUSED:
    #         b.text = "Resume playing"
    #         b.on_click = lambda e: audio1.resume()

    #     elif e.state == ft.AudioState.PLAYING:
    #         b.text = "Pause playing"
    #         b.on_click = lambda e: audio1.pause()

    #     b.update()
    # audio1 = ft.Audio(
    #     src="D:/music/ADHD_ADD Relief - WHITE NOISE - Natural Sound For Better Focus And Sleep (Proven by Science)(MP3_160K).mp3",
    #     autoplay=True,
    #     on_state_changed=change_button
    # )
    # b = ft.ElevatedButton("Pause playing", on_click=lambda _: audio1.pause())
    # page.overlay.append(audio1)

    # notafication

    # Timer state
    running = False
    paused = False

    # pygame init
    pygame.init()

    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    loader_circle = LoaderCircle(page)
    content_area = ft.Container(content=loader_circle.content())
    timer_display = TimerDisplay(page=page)
    timer_form = TimerForm(page=page, data=data)
    timer_settings = TimerSettings(
        page=page,
        data=[
            data.get("start"),
            data.get("end"),
            data.get("bg_music"),
        ],
    )

    timer_form.get_timer_settings().on_click = lambda e: page.open(timer_settings.dlg)
    # timer_form.get_timer_settings().on_click = lambda e: page.open(timer_form.dlg)

    timer_form.get_timer_start().on_click = lambda e: startTimer()
    timer_display.get_btn_stop().on_click = lambda e: stopTimer()
    timer_display.get_btn_pause().on_click = lambda e: pauseTimer(page)

    def update_timer_display(status, minutes, seconds):
        print(f"{minutes:02d}:{seconds:02d}")
        timer_display.get_timer_display().value = f"{minutes:02d}:{seconds:02d}"
        timer_display.get_session().value = status
        page.update()

    def countdown(session, study, breaks):
        nonlocal running, paused
        total_study_seconds = study * 60
        total_break_seconds = breaks * 60
        sessionFound = 1
        while sessionFound <= session and running:
            # start timer sound here
            pygame.mixer.music.load(getPath("assets/start_sound.mp3"))
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
            time.sleep(6)
            pygame.mixer.music.load(data["bg_music"])
            pygame.mixer.music.set_volume(0.3)
            pygame.mixer.music.play()
            # study loops
            while total_study_seconds > 0 and running:
                if not paused:
                    mins, sec = divmod(total_study_seconds, 60)
                    update_timer_display(
                        "Study (" + str(sessionFound) + ":" + str(session) + ")",
                        mins,
                        sec,
                    )
                    time.sleep(1)
                    total_study_seconds -= 1
                else:
                    time.sleep(1)
            # break loops

            pygame.mixer.music.load(getPath("assets/finish_sound.mp3"))
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
            time.sleep(7)
            while total_break_seconds > 0 and running:
                if not paused:
                    mins, sec = divmod(total_break_seconds, 60)
                    update_timer_display(
                        "Break (" + str(sessionFound) + ":" + str(session) + ")",
                        mins,
                        sec,
                    )
                    total_break_seconds -= 1
                    time.sleep(1)
                else:
                    time.sleep(1)
            sessionFound += 1
            total_study_seconds = study * 60
            total_break_seconds = breaks * 60
            pygame.mixer.music.stop()
        pygame.mixer.music.stop()
        if running:
            # update_timer_display("End",0, 0)
            Route(timer_form.content)

    def startTimer():
        nonlocal running, paused
        running = True
        paused = False
        study_time = int(timer_form.get_timer_minutes().value)
        break_time = int(timer_form.get_timer_break().value)
        session = int(timer_form.get_timer_sessions().value)
        notification.notify(
            title="Timer start",
            message="Timer is start end after " + str(study_time),
            timeout=3,
            app_icon=icon_path,
        )
        Route(timer_display.content)
        # pygame.mixer.music.load(data['start'])
        # pygame.mixer.music.set_volume(0.3)
        # pygame.mixer.music.play()
        # time.sleep(4)
        # pygame.mixer.music.load(data['bg_music'])
        # pygame.mixer.music.play()
        savedTimer()
        threading.Thread(
            target=countdown, args=(session, study_time, break_time), daemon=True
        ).start()
        print("thread is start")

    def savedTimer():
        data = {
            "study": timer_form.get_timer_minutes().value,
            "break": timer_form.get_timer_break().value,
            "session": timer_form.get_timer_sessions().value,
        }
        timerModel.saveData(data)

    def pauseTimer(page):
        nonlocal paused
        paused = not paused
        if not paused:
            pygame.mixer.music.play()
        else:
            pygame.mixer.music.pause()
        timer_display.get_btn_pause().text = "Start" if paused else "Pause"
        if paused:
            notification.notify(
                title="Timer Paused",
                message="Timer is Paused",
                timeout=3,
                app_icon=icon_path,
            )
        page.update()

    def stopTimerSound():
        time.sleep(2)
        pygame.mixer.music.stop()

    def stopTimer():
        nonlocal running, paused
        running = False
        paused = False
        Route(timer_form.content)
        threading.Thread(target=stopTimerSound, daemon=True).start()

    def Route(content):
        content_area.content = content()
        page.update()

    # Custom Title Bar
    custom_title_bar = ft.Container(
        content=ft.Row(
            [
                ft.WindowDragArea(
                    content=ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("My App", size=16),
                                ft.IconButton(
                                    icon=ft.icons.CLOSE,
                                    on_click=lambda e: page.window.close(),
                                ),
                            ]
                        ),
                        height=50,
                        bgcolor=ft.Colors.BLUE_GREY_500,
                    ),
                    height=50,
                    expand=True,
                )
            ],
            alignment="center",
        ),
        height=50,
        bgcolor=ft.Colors.BLUE_GREY_400,
    )

    # page.add(custom_title_bar)
    page.add(
        ft.Column(
            [
                content_area,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
    )
    time.sleep(5)
    content_area.content = timer_form.content()
    page.update()


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
