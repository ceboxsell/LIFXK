import sys
# import xbmc
# import xbmcgui
# import xbmcaddon
import os
import subprocess
import logging
from time import sleep
from subprocess import call

import requests
import json
import ConfigParser
lifxCloud = 'https://api.lifx.com/v1/'

def _log(data):
    #if loglevel == 'trace':
    #    LF.write('**** ' + str(data) + ' ****\n')
    logging.debug(data)

def checkIfMovie():
    _log('Check if Movie')
    isTVorMovieQuery = {'jsonrpc': '2.0', 'method': 'Player.GetItem', 'params': {'properties': ['showtitle', 'season', 'episode'], 'playerid': 1}, 'id': 'VideoGetItem'}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(isTVorMovieQuery)))
    if response['result']['item']['season'] == -1:
        return True
    else:
        return False

def getSceneList(movie, tv, pause):
    global setSceneTV
    global setSceneMovie
    _log('Get Scenes')
    getAvailableScenes = requests.get(lifxCloud + 'scenes', headers=header)
    _log(getAvailableScenes.url)
    _log(getAvailableScenes.status_code)
    if getAvailableScenes.status_code == requests.codes.ok:
        availableScenes = json.loads(getAvailableScenes.text)
        scene_names = {}
        for scene in availableScenes:
            if scene['name'] == movie:
                scene_names.update({'Movie': scene['uuid']})
            if scene['name'] == tv:
                scene_names.update({'TV': scene['uuid']})
            if scene['name'] == pause:
                scene_names.update({'Pause': scene['uuid']})
        _log('the scene names are ' + str(scene_names))
        setSceneTV = lifxCloud + 'scenes/scene_id:' + scene_names['TV'] + '/activate'
        setSceneMovie = lifxCloud + 'scenes/scene_id:' + scene_names['Movie'] + '/activate'
        if scene_names['Pause']:
            setScenePause = lifxCloud + 'scenes/scene_id:' + scene_names['Pause'] + '/activate'
        else:
            setScenePause = False
        _log('Scene TV ' + setSceneTV + ' Scene Movie ' + setSceneMovie + ' Pause ' + setScenePause)
    else:
        if getAvailableScenes.status_code == 401:
            logging.warning('******* Error connecting ')
            """ Error on the connection """
            getAvailableScenes.raise_for_status()

def getLightState(name, type='label'):
    """ This function checks what lights are in the group and what color they are currently set to """
    _log('Get Light State')
    if name == 'all':
        getAvailableLights = requests.get(lifxCloud + 'lights/' + name, headers=header)
        _log(getAvailableLights.url)
    else:
        getAvailableLights = requests.get(lifxCloud + 'lights/' + type + ':' + name, headers=header)
        _log(getAvailableLights.url)
        
    if getAvailableLights.status_code == requests.codes.ok:
        availableLights = json.loads(getAvailableLights.text)
        #_log(str(availableLights))
        info = []
        for light in availableLights:
            info.append({'id': light['id'], 'label': light['label'], 'power': light['power'], 'hue': light['color']['hue'], 'saturation': light['color']['saturation'],'kelvin': light['color']['kelvin'],'brightness': light['brightness']})
        return info
    return False

def compareLightState(sceneStateLights):
    """this will check the current state to the state found to the one post scene. If it has changed then we will not restore lights """
    changeLights = True
    currentState = getLightState(bulbs['set'], bulbs['type'])
    _log('The scene state then current state')
    _log(currentState)
    _log(sceneStateLights)
    if sceneStateLights == []:
        return True
    for light in currentState:
        for sLight in sceneStateLights:
            if light['label'] == sLight['label']:
                _log('Label is the same')
                if light['power'] == sLight['power'] and light['hue'] == sLight['hue'] and light['saturation'] == sLight['saturation'] and light['brightness'] == sLight['brightness'] and light['kelvin'] == sLight['kelvin']:
                    changeLights = True
                    _log('Lights state is True')
                else:
                    _log('Lights changed so set to False')
                    changeLights = False
            else:
                _log('Label is not the same')
    _log('change Lights = ' + str(changeLights))
    return changeLights
                
def restoreLights(LightStates, duration=5):
    """ This function's purpose is to set the lights to a given HSK from what they once were"""
    _log('RestoreLights LightStates are ' + str(LightStates))
    options = []
    #option = {'states':[]}
    _log(str(options))
    for light in LightStates:
        if(str(light['saturation']) == '0.0'):
            options.append({'selector':'id:' + str(light['id']),'color':'hue:' + str(light["hue"]) + ' saturation:' + str(light['saturation']) + ' kelvin:' + str(light['kelvin']),'brightness':str(light['brightness']),'duration':duration,'power':str(light['power'])})
        else:
            options.append({'selector':'id:' + str(light['id']),'color':'hue:' + str(light["hue"]) + ' saturation:' + str(light['saturation']),'brightness':str(light['brightness']),'duration':duration,'power':str(light['power'])})
    option = {'states':options}
    _log(str(option))
    chooseBulb = lifxCloud + 'lights/states'
    r = requests.put(chooseBulb, json=option, headers=header)
    _log(r.url)
    _log(r.text)    

def checkIfOff(LightStates):
    """ This will check if the lights were turned off before playing. If so don't change the state of the lights leave off """
    _log('Check if lights turned off')
    power = False
    for light in LightStates:
            if light['power'] == 'off':
                power = False
                _log(str(light['label']) + ' power is off')
            else:
                power = True
                _log(str(light['label']) + ' power is on')
    if power:
        return True
    else:
        return False
                

def turnOff(name, type='label', duration=5):
    """ This function turns off a given group or light """
    _log('Turn Off')
    powerCommand = lifxCloud + '/' + type + ':' + name + '/state'
    option = {'power': 'off', 'duration': duration}
    requests.put(powerCommand, params=option, headers=header)
    return

def setSceneLightState(delay):
    global sceneLightState
    sceneLightState = []
    sleep(delay+1)
    _log('get scene state for comparison, sleep was ' + str(delay+1))
    sceneLightState = getLightState(type=bulbs['type'], name=bulbs['set'])
    _log(sceneLightState)

def loadConfig ():
    global header
    global headerAuth
    global bulbs
    global setColor
    global config
    global setScenePause
    global movie_scene
    global tv_scene
    global loglevel
    global delay_movie_start
    global delay_TV_start
    global delay_pause
    global delay_resume
    global delay_end_play
    global pause_scene
    global scene_state_delay
    global LF
    global logFile
    
    confpath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'lifx.cfg')
    config = ConfigParser.RawConfigParser()
    config.readfp(open(confpath))
    loglevel = config.get('Logging','level')
    logFile = config.get('Logging','FileName')
       
    #_log('load config')
    
    apiKey = config.get('Authentication', 'apiKey')
    apiKey = 'Bearer ' + apiKey
    header = {'content-type': 'application/json', 'authorization': apiKey}
    headerAuth = {'authorization': apiKey}

    bulbs = {'type': config.get('Bulbs', 'type'), 'set': config.get('Bulbs', 'set')}
    bulbURL = bulbs['type'] + ':' + bulbs['set']

    movie_scene = config.get('Scenes','movie_scene')
    tv_scene = config.get('Scenes','tv_scene')
    pause_scene = config.get('Scenes','pause_scene')
    
    loglevel = config.get('Logging','level')

    delay_movie_start = config.get('Delay','MovieStart')
    delay_TV_start = config.get('Delay','TVStart')
    delay_pause = config.get('Delay','Pause')
    delay_resume = config.get('Delay','Resume')
    delay_end_play = config.get('Delay','EndPlay')
    scene_state_delay = 0
	
def main():
    loadConfig()
    logging.basicConfig(filename=os.getenv('APPDATA') + '\\Kodi\\' + logFile, filemode='w', format='%(asctime)s %(message)s' , level=getattr(logging,loglevel.upper()))
    preVideoLightState = []
    sceneLightState = []
    getSceneList(movie_scene, tv_scene, pause_scene)
    
if __name__ == '__main__':
    main()




 
class XBMCPlayer(xbmc.Player):
    def __init__(self, *args):
        pass
    
    def onPlayBackStarted(self):
        global preVideoLightState
        global sceneLightState
        _log('****** Playback Started')
        preVideoLightState = getLightState(bulbs['set'], bulbs['type'])
        _log('** the light state before playing is ' + str(preVideoLightState))
        if checkIfOff(preVideoLightState):
            if checkIfMovie():
                _log('Movie')
                delay = {'duration':delay_movie_start}
                scene_state_delay = delay_movie_start
                r = requests.put(setSceneMovie, params=delay, headers=headerAuth)
                _log(r.url)
                _log(r.text)
            else:
                _log('TV')
                delay = {'duration':delay_TV_start}
                scene_state_delay = delay_TV_start
                r = requests.put(setSceneTV, params=delay, headers=headerAuth)
                _log(r.url)
                _log(r.text)
            sleep(int(scene_state_delay)+1)
            _log('get scene state for comparison, sleep was ' + scene_state_delay)
            sceneLightState = getLightState(bulbs['set'], bulbs['type'], )
            _log(sceneLightState)
        else:
            _log('Lights are off so stay off')

    """ On playback resumed like start we assume that you want the lights to change to the scene again no matter what """

    def onPlayBackResumed(self):
        _log('Playback Resumed')
        global preVideoLightState
        _log('Check if off')
        if checkIfOff(preVideoLightState):
            delay = {'duration':delay_resume}
            sceneLightState = []
            scene_state_delay = int(delay_resume)
            if checkIfMovie():
                r = requests.put(setSceneMovie, params=delay, headers=headerAuth)
                _log(r.text)
                _log(r.url)
                _log('Delay and store new scene state')
                setSceneLightState(scene_state_delay)
            else:
                r = requests.put(setSceneTV, params=delay, headers=headerAuth)
                _log(r.url)
                _log(r.text)
                _log('Delay and store new scene state')
                setSceneLightState(scene_state_delay)
                
        else:
            _log('Lights stay off')
            
    def onPlayBackEnded(self):
        global preVideoLightState
        _log('Playback ended')
        if checkIfOff(preVideoLightState):
            if compareLightState(sceneLightState):
                restoreLights(preVideoLightState, delay_end_play)
            else:
                _log('the lights state had changed from the scene to something else so leave alone')
        else:
            _log('On ended the lights remain off')
        getSceneList(movie_scene, tv_scene, pause_scene)
            
    def onPlayBackPaused(self):
        global preVideoLightState
        global sceneLightState
        _log('Playback paused')
        if checkIfOff(preVideoLightState):
            scene_state_delay = int(delay_pause)
            if compareLightState(sceneLightState):
                if setScenePause:
                    _log('Scene Pause exists')
                    delay = {'duration':delay_pause}
                    r = requests.put(setScenePause, params=delay, headers=headerAuth)
                    _log(r.url)
                    _log(r.text)
                    setSceneLightState(scene_state_delay)
                else:
                    _log('Scene Pause does not exist')
                    restoreLights(preVideoLightState, delay_pause)
                    sceneLightState = []
                    setSceneLightState(scene_state_delay)
            else:
                _log('Lights have changed so ignore pause change')
        else:
            _log('Lights remain off on pause')
    
    def onPlayBackStopped(self):
        global preVideoLightState
        _log('Playback stopped')
        if checkIfOff(preVideoLightState):
            if compareLightState(sceneLightState):
                _log('Lights have not changed so restore lights')
                restoreLights(preVideoLightState, delay_end_play)
            else:
                _log('Lights state has changed since playback started so we do not return to original state')
        else:
                _log('Lights are off on stop')
        getSceneList(movie_scene, tv_scene, pause_scene)

player = XBMCPlayer()

while(not xbmc.abortRequested):
    xbmc.sleep(100)
