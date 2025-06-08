import threading
import time

import flet as ft
from flet import (ElevatedButton, Page, Text, Column, Row)

import timerModel


class TimerDisplay:
    def __init__(self, page: Page):
        self.page = page
        self.timerMinutes = 0
        self.session = Text("Start Timer", size=25, weight=ft.FontWeight.BOLD, color='green')
        self.timer_display = Text("00:00", size=48, weight=ft.FontWeight.BOLD, color='green')
        # self.btnStart = ElevatedButton('Start', on_click=lambda e: self.study_timer())
        self.btnPause = ElevatedButton('Pause')
        self.btnStop = ElevatedButton('Stop')
        # self.btnBack = ElevatedButton('Back')

    def content(self)-> Column:
        return Column([
            self.session,
            self.timer_display,
            Row([
                # self.btnStart,
                self.btnPause,
                self.btnStop,
                # self.btnBack,
            ],
                alignment=ft.MainAxisAlignment.CENTER),
        ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def study_timer(self):
        print("Study Timer is start")

    # Getters
    def get_page(self):
        return self.page

    def get_session(self):
        return self.session

    def get_timer_display(self):
        return self.timer_display

    def get_btn_start(self):
        return self.btnStart

    def get_btn_pause(self):
        return self.btnPause

    def get_btn_stop(self):
        return self.btnStop

    def get_btn_back(self):
        return self.btnBack




def header(page: Page, backFn=''):
    data = timerModel.loadData()

    session = int(data.get("total"))
    studyTime = int(data.get('study')) * 60
    breakTime = int(data.get('break')) * 60

    timer = Text(f"00:00", size=48, weight=ft.FontWeight.BOLD, color='green')
    mins, sesc = divmod(studyTime, 60)
    timer.value = f"{mins:02d}:{sesc:02d}"
    # buttons = {
    #     "start": ElevatedButton('Start'),
    #     "pause": ElevatedButton('Pause', disabled=True),
    #     "stop": ElevatedButton('Stop', disabled=True)
    # }

    # timer status
    timer_status = Text("", size=58, weight=ft.FontWeight.NORMAL, color='blue')

    buttons = [
        ElevatedButton('Start', on_click=lambda e: study_timer()),
        ElevatedButton('Pause'),
        ElevatedButton('Stop'),
    ]

    def startTimer(studyTime, breaktime, timer_status, session):
        sessionEnd = 1
        while (session > 0):
            timer_status.value = "Start Session: " + str(sessionEnd)
            page.update()
            while (studyTime > 0):
                mins, sesc = divmod(studyTime, 60)
                timer.value = f"{mins:02d}:{sesc:02d}"
                studyTime -= 1
                time.sleep(1)
                page.update()

            timer_status.value = "Break Session: " + str(sessionEnd)
            page.update()
            while (breaktime > 0):
                mins, sesc = divmod(breaktime, 60)
                timer.value = f"{mins:02d}:{sesc:02d}"
                breaktime -= 1
                time.sleep(1)
                page.update()
            sessionEnd += 1
            session -= 1
            page.update()

    def study_timer():
        print("Study Timer")
        threading.Thread(target=startTimer, args=(studyTime, breakTime, timer_status, session,), daemon=True).start()

    content = Column([
        timer_status,
        timer,
        Row(buttons, alignment=ft.MainAxisAlignment.CENTER),
    ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return {
        "buttons": buttons,
        "timer_display": timer,
        "content": content
    }
