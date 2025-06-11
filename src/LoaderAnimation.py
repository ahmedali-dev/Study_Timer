from flet import (
    Container,
    Row,
    Column,
    alignment,
    Animation,
    Page,
    MainAxisAlignment,
    CrossAxisAlignment,
)
import asyncio


class LoaderCircle:
    def __init__(self, page: Page):
        self.page = page
        self.circle = Container(
            width=100,
            height=100,
            bgcolor="green",
            border_radius=50,
            alignment=alignment.center,
            animate=Animation(1000, "easeInOut"),  # 👈 smooth width/height animation
            animate_rotation=Animation(1000, "linear"),  # 👈 smooth rotation
        )

    async def auto_rotate(self):
        while True:
            await asyncio.sleep(1)  # Wait before next rotation

            if self.circle.width == 100 and self.circle.height == 100:
                self.circle.width = 50
                self.circle.height = 50
                self.circle.bgcolor = "blue"
            else:
                self.circle.width = 100
                self.circle.height = 100
                self.circle.bgcolor = "green"
            self.circle.rotate = (
                (self.circle.rotate + 360) if self.circle.rotate else 360
            )
            self.page.update()

    def content(self) -> Column:
        self.page.run_task(self.auto_rotate)
        return Column(
            [
                Row([self.circle], alignment=MainAxisAlignment.CENTER),
            ],
            alignment=MainAxisAlignment.CENTER,  # Vertical centering
            horizontal_alignment=CrossAxisAlignment.CENTER,
            expand=True,
        )


"""def main(page: ft.Page):
    circle = ft.Container(
        width=100,
        height=100,
        bgcolor="green",
        border_radius=50,
        alignment=ft.alignment.center,
        animate=ft.Animation(1000, "easeInOut"),  # 👈 smooth width/height animation
        animate_rotation=ft.Animation(1000, "linear"),  # 👈 smooth rotation
    )

    async def auto_rotate():
        while True:
            await asyncio.sleep(1)  # Wait before next rotation

            if circle.width == 100 and circle.height == 100:
                circle.width = 50
                circle.height = 50
                circle.bgcolor = "blue"
            else:
                circle.width = 100
                circle.height = 100
                circle.bgcolor = "green"
            circle.rotate = (circle.rotate + 360) if circle.rotate else 360
            page.update()

    page.add(
        ft.Column(
            [
                ft.Text("Loading..."),
                ft.Row([circle], alignment=ft.MainAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.CENTER,  # Vertical centering
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
    )

    page.run_task(auto_rotate)  # Start the rotation loop


ft.app(target=main)
"""
