import flet
from flet import (TextField, Row, MainAxisAlignment, Container, AlertDialog, Column, Text, ElevatedButton,
                  CrossAxisAlignment, alignment, padding, Page)
from pygments.styles.dracula import background


class TimerForm:
    def __init__(self, page, data={"study": 50, "break": 10,"session": 4}):
        self.page = page
        self.timerMinutes = TextField(label="Study (min)", value=data['study'], width=100, border_color='green')
        self.timerBreak = TextField(label="Break (min)", value=data['break'], width=100, border_color='green')
        self.timerSessions = TextField(label="Sessions", value=data['session'], width=100, border_color='green')
        self.startTimer = ElevatedButton("start timer", bgcolor='green',color='black')
        self.settings = ElevatedButton('🕹', bgcolor='blue')

        self.dlg = AlertDialog(
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

    def content(self) -> Container:
        return Container(
            content=Column(
                [
                    Row(
                        [self.timerMinutes, self.timerBreak, self.timerSessions],
                        alignment=MainAxisAlignment.CENTER,
                    ),
                    Container(
                        content=Row([
                            self.startTimer,
                            self.settings,
                        ], alignment=MainAxisAlignment.CENTER),
                        alignment=flet.alignment.center,
                        margin=flet.margin.all(10),
                    )
                ]
            )
            ,
            expand=False,
            padding=20,
        )

    # Getters
    def get_page(self):
        return self.page

    def get_timer_minutes(self):
        return self.timerMinutes

    def get_timer_break(self):
        return self.timerBreak

    def get_timer_sessions(self):
        return self.timerSessions

    def get_timer_start(self):
        return self.startTimer

    def get_timer_settings(self):
        return self.settings


def inputs(page: Page):
    # Timer settings
    study_minutes = TextField(label="Study (min)", value="50", width=100, border_color='green')
    break_minutes = TextField(label="Break (min)", value="10", width=100, border_color='green')
    total_sessions = TextField(label="Sessions", value="4", width=100, border_color='green')

    content = Container(
        content=Row(
            [study_minutes, break_minutes, total_sessions],
            alignment=MainAxisAlignment.CENTER,
        ),
        expand=False,
        padding=20
    )

    dealog = AlertDialog(
        title=Text("input validation"),
        content=Column(
            [
                Text("Input Validation Error"),
                ElevatedButton("Close", on_click=lambda e: page.close(dealog)),
            ],
            expand=False,
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER,
            height=50,
        ),

        alignment=alignment.center,
        title_padding=padding.all(15),
    )

    return {
        "Study_Minutes": study_minutes,
        "Break_Minutes": break_minutes,
        "Total_Sessions": total_sessions,
        "content": content,
        'input_dlg': dealog,
    }
