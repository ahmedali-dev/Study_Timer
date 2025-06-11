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
    """ Get absolute path to resource, works for dev and PyInstaller """
    try:
        base_path = sys._MEIPASS  # PyInstaller temporary folder
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def main(page: ft.Page):
    page.title = "Study Timer"
    icon_path = resource_path("assets/icon.ico")
    page.window.width = 800
    page.window.height = 500
    # page.set_ic
    data = timerModel.loadData()

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
            pygame.mixer.music.load(data["bg_music"])
            pygame.mixer.music.play()
            # study loops
            while total_study_seconds > 0 and running:
                if not paused:
                    mins, sec = divmod(total_study_seconds, 60)
                    update_timer_display("Study (" + str(sessionFound) + ":" + str(sessionFound) + ")", mins, sec)
                    time.sleep(1)
                    total_study_seconds -= 1
                else:
                    time.sleep(1)
            # break loops

            pygame.mixer.music.load(data["end"])
            pygame.mixer.music.play()
            while total_break_seconds > 0 and running:
                if not paused:
                    mins, sec = divmod(total_break_seconds, 60)
                    update_timer_display("Break ("+ str(sessionFound) + ":" + str(sessionFound) + ")", mins, sec)
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
        Route(timer_display.content)
        notification.notify(
            title="Timer start",
            message="Timer is start end after " + str(study_time),
            timeout=3,
            app_icon=icon_path
        )
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
                app_icon=icon_path
            )
        page.update()

    def stopTimerSound():
        time.sleep(2)
        # pygame.mixer.music.stop()

    def stopTimer():
        nonlocal running, paused
        running = False
        paused = False
        Route(timer_form.content)
        threading.Thread(target=stopTimerSound, daemon=True).start()

    def Route(content):
        content_area.content = content()
        page.update()

    page.add(
        ft.Column(
            [
                # timer_display.content(),
                # timer_form.content(),
                content_area
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    time.sleep(5)
    content_area.content = timer_form.content()
    page.update()


"""
    def defaultPage(e):
        content_area.content = ft.Container(
            content=ft.Column(
                [
                    inputContent.get("content"),
                    ft.Row([
                        ft.ElevatedButton("start timer", on_click=goToStartTimer),
                        ft.ElevatedButton('🕹', on_click=goToSettings),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.alignment.center,
            padding=20,
        )
        page.update()

    settingsContent = settings(page, defaultPage)

    def goToStartTimer(e):
        # check input content is valid
        page.update()

        inputs_validation = (inputContent.get("Study_Minutes").value == ""
                             or inputContent.get("Break_Minutes").value == ""
                             or inputContent.get("Total_Sessions").value == ""
                             )


        if (
                inputs_validation
        ):
            page.open(inputContent.get('input_dlg'))
            return

        #saved input value
        timerDataUpdate = {
            "study": int(inputContent.get("Study_Minutes").value),
            "break": int(inputContent.get("Break_Minutes").value),
            "total": int(inputContent.get("Total_Sessions").value),
        }
        timerModel.saveData(timerDataUpdate)

        pg.mixer.music.load(data.get('bg_music'))
        pg.mixer.music.set_volume(0.3)
        pg.mixer.music.play()
        content_area.content = headerContent.get('content')
        page.update()




    def goToSettings(e):
        content_area.content = settingsContent.get('content')
        page.update()





    content_area = ft.Container(
        content=ft.Column(
            [
                inputContent.get("content"),
                ft.Row([
                    ft.ElevatedButton("start timer", on_click=goToStartTimer),
                    ft.ElevatedButton('🕹', on_click=goToSettings),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
    )

    page.add(content_area)
    
    
    AlertDialog(
            title=Text("input validation"),
            content=Column(
                [
                    Text("Input Validation Error"),
                    ElevatedButton("Close", on_click=lambda e: page.close(self.dlg)),
                ],
                expand=False,
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
                height=50,
            ),
            
        
        
            alignment=alignment.center,
            title_padding=padding.all(15),
        )
"""

if __name__ == "__main__":
    ft.app(target=main,assets_dir="assets")

