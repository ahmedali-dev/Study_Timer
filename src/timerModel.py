import json
import os
def getSettingPath():
    settingsPath = os.path.join(os.getcwd(), 'src', 'timer_settings.json')
    if os.path.exists(settingsPath):
        return settingsPath
    else:
        print('file not found')
        return False
def loadData():
    data = getSettingPath()
    if not data:
        return {
            "study": 50,
            "break": 10,
            "total": 4,
            "start": "D:\\Project\\timerElectorn\\endSession.mp3",
            "end": "E:/Project/timerTkenter/start.wav",
            "bg_music": "D:/music/ADHD_ADD Relief - WHITE NOISE - Natural Sound For Better Focus And Sleep (Proven by Science)(MP3_160K).mp3",
            "bg_music_volume": 0.54,
            "file": False
        }

    with open(data) as json_file:
        return  json.load(json_file)

def saveData(data):
    load = loadData()
    if load.get('file') == False:
        return load

    print(data)
    settingPath = getSettingPath()
    newData = {**load, **data}

    with open(settingPath, 'w') as json_file:
        json.dump(newData, json_file, indent=4)

