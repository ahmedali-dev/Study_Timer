from flet import (
    Page, FilePicker, FilePickerResultEvent, Column, Container, padding, alignment, ScrollMode,
    Text, TextField, FilledButton, OutlinedButton, MainAxisAlignment, CrossAxisAlignment, AlertDialog
)

import timerModel
import sqlite3


class TimerSettings:
    def __init__(self, page: Page, data=[0, 0, 0], on_test_notification=None, store=None):
        self.page = page
        self.store = store

        # Define inputs
        # self.startSound = TextField(value='Path: ' + str(data[0]), disabled=True)
        # self.endSound = TextField(value='Path: ' + str(data[1]), disabled=True)
        self.bgMusic = TextField(value=str(data[2]), label="Background music", disabled=True, width=430)

        # Define buttons
        # self.btnS = ElevatedButton('Start sound', bgcolor='green', color='black', on_click=lambda e: self.pickerStart.pick_files())
        # self.btnE = ElevatedButton('End sound', bgcolor='green', color='black', on_click=lambda e: self.pickerEnd.pick_files())
        self.btnB = FilledButton('Choose audio file', icon='folder_open', on_click=lambda e: self.pickerBg.pick_files())
        self.close = OutlinedButton('Done', on_click=lambda _: page.close(self.dlg))
        self.testNotification = OutlinedButton('Test notification', icon='notifications_outlined', on_click=on_test_notification)
        self.notificationStatus = Text('Session alerts use your system notification settings.', size=12)

        # file picker
        # self.pickerStart = FilePicker(on_result=self.onPickStart)
        # self.pickerEnd = FilePicker(on_result=self.onPickEnd)
        self.pickerBg = FilePicker(on_result=self.onPickBg)

        # page.overlay.append(self.pickerStart)
        # page.overlay.append(self.pickerEnd)
        page.overlay.append(self.pickerBg)

        # dealog
        self.dlg = AlertDialog(
            title=Text('Sound & notifications', weight='w700'),
            content=self.content(),
            title_padding=padding.only(left=24, top=20, right=24),
            content_padding=padding.all(24),
            alignment=alignment.center,
        )

    def content(self) -> Column:
        return Column([
            # self.Con([self.startSound, self.btnS]),
            # self.Con([self.endSound, self.btnE]),
            self.Con([self.bgMusic, self.btnB]),
            self.Con([self.testNotification, self.notificationStatus]),
            self.Con([self.close]),
        ],
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER,
            expand=False,
            height=310,
            width=520,
            scroll=ScrollMode.AUTO
        )

    # def onPickStart(self,e: FilePickerResultEvent):
    #     if self.saveFilePick(e,'start'):
    #         self.startSound.value = e.files[0].path
    #         self.page.update()
    # def onPickEnd(self,e: FilePickerResultEvent):
    #     if self.saveFilePick(e,'end'):
    #         self.endSound.value = e.files[0].path
    #         self.page.update()
    def onPickBg(self,e: FilePickerResultEvent):
        if self.saveFilePick(e,'bg_music'):
            self.bgMusic.value = e.files[0].path
            self.page.update()

    def checkMediaFile(self,file)->bool:
        extensionAllow = ['mp3', 'wav', 'm4a']
        return file.split('.')[-1] in extensionAllow
    
    def saveFilePick(self,e: FilePickerResultEvent, key):
        if e.files:
            # check is a media file
            file = e.files[0].path
            print(file)
            if self.checkMediaFile(file):
                print('file is saved')
                try:
                    timerModel.saveData({f'{key}': file}, self.store)
                except (OSError, sqlite3.Error):
                    self.notificationStatus.value = 'Could not save this audio preference.'
                    self.page.update()
                    return False
                return True
        return False
    def Con(self, content):
        return Container(
            content=Column(
                content,
                alignment=MainAxisAlignment.CENTER,
            ),
            margin=5
        )


