from flet import (
    Page, FilePicker, FilePickerResultEvent, Column, Container, padding, alignment,ScrollMode,
    Text, TextField, ElevatedButton, MainAxisAlignment, CrossAxisAlignment, CupertinoFilledButton, AlertDialog
)

import timerModel


class TimerSettings:
    def __init__(self, page: Page, data=[0, 0, 0]):
        self.page = page

        # Define inputs
        self.startSound = TextField(value='Path: ' + str(data[0]), disabled=True)
        self.endSound = TextField(value='Path: ' + str(data[1]), disabled=True)
        self.bgMusic = TextField(value='Path:' + str(data[2]), disabled=True)

        # Define buttons
        self.btnS = ElevatedButton('Start sound', bgcolor='green', color='black', on_click=lambda e: self.pickerStart.pick_files())
        self.btnE = ElevatedButton('End sound', bgcolor='green', color='black', on_click=lambda e: self.pickerEnd.pick_files())
        self.btnB = ElevatedButton('Background music', bgcolor='green', color='black', on_click=lambda e: self.pickerBg.pick_files())
        self.close = ElevatedButton('Back', bgcolor='#FF3F33', color='black', on_click=lambda _: page.close(self.dlg))

        # file picker
        self.pickerStart = FilePicker(on_result=self.onPickStart)
        self.pickerEnd = FilePicker(on_result=self.onPickEnd)
        self.pickerBg = FilePicker(on_result=self.onPickBg)

        page.overlay.append(self.pickerStart)
        page.overlay.append(self.pickerEnd)
        page.overlay.append(self.pickerBg)

        # dealog
        self.dlg = AlertDialog(
            title=Text('Timer Settings', text_align=alignment.center),
            content=self.content(),
            title_padding=padding.all(5),
            content_padding=padding.all(5),
            alignment=alignment.center,
        )

    def content(self) -> Column:
        return Column([
            self.Con([self.startSound, self.btnS]),
            self.Con([self.endSound, self.btnE]),
            self.Con([self.bgMusic, self.btnB]),
            self.Con([self.close]),
        ],
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER,
            expand=False,
            height=370,
            width=500,
            scroll=ScrollMode.AUTO
        )

    def onPickStart(self,e: FilePickerResultEvent):
        if self.saveFilePick(e,'start'):
            self.startSound.value = e.files[0].path
            self.page.update()
    def onPickEnd(self,e: FilePickerResultEvent):
        if self.saveFilePick(e,'end'):
            self.endSound.value = e.files[0].path
            self.page.update()
    def onPickBg(self,e: FilePickerResultEvent):
        if self.saveFilePick(e,'bg_music'):
            self.bgMusic.value = e.files[0].path
            self.page.update()

    def checkMediaFile(self,file)->bool:
        extensionAllow = ['mp3','vaw', 'm4a']
        return file.split('.')[-1] in extensionAllow
    
    def saveFilePick(self,e: FilePickerResultEvent, key):
        if e.files:
            # check is a media file
            file = e.files[0].path
            print(file)
            if self.checkMediaFile(file):
                print('file is saved')
                timerModel.saveData({f'{key}': file})
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


def settings(page: Page, backFn):
    # loading saved path
    data = timerModel.loadData()
    # Define UI elements first so they can be updated inside callbacks
    timer_start_sound_path = Text('Timer Start Sound' + data.get('study_start'))
    timer_end_sound_path = Text('Timer End Sound' + data.get('study_end'))
    timer_background_sound_path = Text('Timer Background Sound' + data.get('bg_music'))

    # button for handle picker file
    timer_start_sound_button = ElevatedButton('select start sound', on_click=lambda e: timer_start_sound.pick_files())
    timer_end_sound_button = ElevatedButton('select start sound', on_click=lambda e: timer_end_sound.pick_files())
    timer_background_sound_button = ElevatedButton('select start sound',
                                                   on_click=lambda e: timer_background_sound.pick_files())

    def on_file_selected_start(e: FilePickerResultEvent):
        print('start', e.files)
        if e.files:
            print("Start sound selected:", e.files[0].path)
            timer_start_sound_path.value = f"Start Sound: {e.files[0].path}"
            data.update({'study_start': e.files[0].path})
            timerModel.saveData(data)
            page.update()

    def on_file_selected_end(e: FilePickerResultEvent):
        print('end', e.files)
        if e.files:
            print("End sound selected:", e.files[0].path)
            timer_end_sound_path.value = f"End Sound: {e.files[0].path}"
            page.update()

    def on_file_selected_background(e: FilePickerResultEvent):
        print('background', e.files)
        if e.files:
            print("Background selected:", e.files[0].path)
            timer_background_sound_path.value = f"Background Sound: {e.files[0].path}"
            page.update()

    # file picker
    timer_start_sound = FilePicker(on_result=on_file_selected_start)
    timer_end_sound = FilePicker(on_result=on_file_selected_end)
    timer_background_sound = FilePicker(on_result=on_file_selected_background)

    # back button
    backButton = CupertinoFilledButton(
        content=Text('Back'),
        opacity_on_click=0.4,
        width=200,
        height=50,
        on_click=lambda e: backFn(e),
    )

    page.overlay.append(timer_start_sound)
    page.overlay.append(timer_end_sound)
    page.overlay.append(timer_background_sound)
    content = Column([
        Container(content=Column([timer_start_sound_path, timer_start_sound_button], alignment=MainAxisAlignment.CENTER,
                                 horizontal_alignment=CrossAxisAlignment.CENTER, ), margin=10),
        Container(content=Column([timer_end_sound_path, timer_end_sound_button], alignment=MainAxisAlignment.CENTER,
                                 horizontal_alignment=CrossAxisAlignment.CENTER, ), margin=10),
        Container(content=Column([timer_background_sound_path, timer_background_sound_button],
                                 alignment=MainAxisAlignment.CENTER,
                                 horizontal_alignment=CrossAxisAlignment.CENTER, ), margin=10),
        backButton,
    ],
        alignment=MainAxisAlignment.CENTER,
        horizontal_alignment=CrossAxisAlignment.CENTER
    )

    return {
        "content": content,
    }
