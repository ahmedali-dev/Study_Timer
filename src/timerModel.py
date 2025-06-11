import json
import os
import sys
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    try:
        base_path = sys._MEIPASS  # PyInstaller temporary folder
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def getSettingPath():
    settingsPath = resource_path("data/timer_settings.json")
    # settingsPath = os.path.join(os.path.dirname(__file__), 'timer_settings.json')
    print(settingsPath)
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
            "session": 4,
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

