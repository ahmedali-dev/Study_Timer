import flet as ft
import asyncio

def main(page: ft.Page):
    DURATION = 3  # total seconds
    INTERVAL = 0.1  # update every 0.1s

    time_text = ft.Text(value=str(DURATION), size=30, weight="bold")
    buttonResetStatus = True
    buttonReset = ft.Button('Click',disabled=True, on_click= lambda e: page.run_task(countdown))
    progress_ring = ft.ProgressRing(
        value=1.0,
        width=150,
        height=150,
        color="green",
        bgcolor="transparent",
        stroke_width=15,  # Default is 4
        stroke_cap="round"
    )


    circle_stack = ft.Stack(
        [
            progress_ring,
            ft.Container(
                content=time_text,
                alignment=ft.alignment.center,
                width=150,
                height=150,
            ),
        ],
        width=150,
        height=150,
    )

    async def countdown():
        global buttonResetStatus
        steps = int(DURATION / INTERVAL)
        for i in range(steps, -1, -1):
            seconds_left = i * INTERVAL
            time_text.value = str(int(seconds_left))  # Display rounded seconds
            progress_ring.value = seconds_left / DURATION
            page.update()
            await asyncio.sleep(INTERVAL)
        buttonReset.disabled = False
        page.update()

    page.add(
        ft.Column(
            [circle_stack,buttonReset
             ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
    )

    page.run_task(countdown)

ft.app(target=main)
