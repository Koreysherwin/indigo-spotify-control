#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spotify Control Plugin for Indigo
Provides comprehensive control and monitoring of Spotify playback
Version 1.0.8 - Spotify Connect active-device detection
"""

import indigo
import time
import subprocess
import json
import re
import threading
import urllib.request
import urllib.parse
import urllib.error
import http.server
import socketserver
import secrets
import hashlib
import base64
import webbrowser

kUpdateFrequencyKey = "updateFrequency"
MIN_UPDATE_FREQUENCY = 2.0
APPLE_SCRIPT_TIMEOUT = 3.0
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:43821/callback"
SPOTIFY_SCOPE = "user-read-playback-state"
BUSY_RESULT = "__BUSY__"


class Plugin(indigo.PluginBase):
    """Main plugin class for Spotify control"""

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.deviceDict = {}
        self.scriptLock = threading.Lock()
        self.connectLock = threading.Lock()
        self.oauthServer = None
        self.oauthState = None
        self.oauthVerifier = None

    def startup(self):
        self.debugLog(u"Spotify Plugin startup called")

    def shutdown(self):
        self.debugLog(u"Spotify Plugin shutdown called")

    def deviceStartComm(self, dev):
        self.debugLog(u"Starting device: " + dev.name)
        updateFreq = max(MIN_UPDATE_FREQUENCY, float(dev.pluginProps.get(kUpdateFrequencyKey, 5)))
        self.deviceDict[dev.id] = {
            'device': dev,
            'updateFrequency': updateFreq,
            'lastUpdate': 0,
            'previousVolume': None,
        }
        self.updateSpotifyStatus(dev)

    def deviceStopComm(self, dev):
        self.debugLog(u"Stopping device: " + dev.name)
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]

    def runConcurrentThread(self):
        try:
            while True:
                currentTime = time.time()
                for devId, devInfo in list(self.deviceDict.items()):
                    dev = devInfo['device']
                    updateFreq = devInfo['updateFrequency']
                    lastUpdate = devInfo['lastUpdate']
                    if currentTime - lastUpdate >= updateFreq:
                        self.updateSpotifyStatus(dev)
                        devInfo['lastUpdate'] = currentTime
                self.sleep(0.25)
        except self.StopThread:
            pass

    def updateSpotifyStatus(self, dev):
        try:
            # Spotify AppleScript reports the app/account playback view, which can
            # reflect a remote Connect session. Keep that legacy state, but publish
            # a separate, API-verified local-device state for automations.
            connectStates = self.getConnectDeviceStates(dev)
            if connectStates:
                dev.updateStatesOnServer(connectStates)
                if dev.pluginProps.get('updateVariables', False):
                    self.updateVariables(dev, connectStates)

            if not self.isProcessRunning("Spotify"):
                dev.updateStatesOnServer([
                    {'key': 'playerState', 'value': 'stopped'},
                    {'key': 'isPlaying', 'value': False},
                    {'key': 'isPaused', 'value': False},
                    {'key': 'isStopped', 'value': True},
                    {'key': 'trackName', 'value': ''},
                    {'key': 'artist', 'value': ''},
                    {'key': 'album', 'value': ''},
                    {'key': 'albumArtist', 'value': ''},
                    {'key': 'trackNumber', 'value': 0},
                    {'key': 'discNumber', 'value': 0},
                    {'key': 'popularity', 'value': 0},
                    {'key': 'artworkUrl', 'value': ''},
                    {'key': 'spotifyUrl', 'value': ''},
                    {'key': 'trackId', 'value': ''},
                    {'key': 'duration', 'value': 0},
                    {'key': 'durationFormatted', 'value': '00:00'},
                    {'key': 'playerPosition', 'value': 0},
                    {'key': 'playerPositionFormatted', 'value': '00:00'},
                    {'key': 'progressPercent', 'value': 0},
                    {'key': 'status', 'value': 'Not Running'}
                ] + connectStates)
                return

            script = r'''
            tell application "Spotify"
                try
                    set playerState to player state as string
                    set soundVol to sound volume
                    set isShuffling to shuffling
                    set isRepeating to repeating
                    if playerState is not equal to "stopped" then
                        set trackName to name of current track
                        set trackArtist to artist of current track
                        set trackAlbum to album of current track
                        set trackDuration to duration of current track
                        set playerPos to player position
                        set trackNumber to track number of current track
                        set discNumber to disc number of current track
                        set trackPopularity to popularity of current track
                        set artworkUrl to artwork url of current track
                        set albumArtist to album artist of current track
                        set spotifyUrl to spotify url of current track
                        set trackId to id of current track
                        set trackName to my replaceText(trackName, "|", "__PIPE__")
                        set trackArtist to my replaceText(trackArtist, "|", "__PIPE__")
                        set trackAlbum to my replaceText(trackAlbum, "|", "__PIPE__")
                        set albumArtist to my replaceText(albumArtist, "|", "__PIPE__")
                        return "SUCCESS:" & playerState & "|" & trackName & "|" & trackArtist & "|" & trackAlbum & "|" & trackDuration & "|" & playerPos & "|" & trackNumber & "|" & discNumber & "|" & trackPopularity & "|" & artworkUrl & "|" & albumArtist & "|" & spotifyUrl & "|" & trackId & "|" & soundVol & "|" & isShuffling & "|" & isRepeating
                    else
                        return "STOPPED|" & soundVol & "|" & isShuffling & "|" & isRepeating
                    end if
                on error errMsg number errNum
                    return "ERROR:" & errNum & ":" & errMsg
                end try
            end tell
            on replaceText(theText, oldString, newString)
                set AppleScript's text item delimiters to oldString
                set textItems to text items of theText
                set AppleScript's text item delimiters to newString
                set theText to textItems as string
                set AppleScript's text item delimiters to ""
                return theText
            end replaceText
            '''
            result = self.executeAppleScript(script, waitForLock=False)
            if result in (None, BUSY_RESULT):
                return

            def safe_int(value, default=0):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return default

            def safe_float(value, default=0.0):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default

            if result.startswith("SUCCESS:"):
                parts = result[8:].split("|")
                if len(parts) < 16:
                    return
                playerState = parts[0]
                trackName = parts[1].replace("__PIPE__", "|")
                artist = parts[2].replace("__PIPE__", "|")
                album = parts[3].replace("__PIPE__", "|")
                albumArtist = parts[10].replace("__PIPE__", "|")
                duration = safe_float(parts[4]) / 1000.0
                position = safe_float(parts[5])
                volume = safe_int(parts[13], 50)
                stateList = [
                    {'key': 'playerState', 'value': playerState},
                    {'key': 'isPlaying', 'value': playerState == 'playing'},
                    {'key': 'isPaused', 'value': playerState == 'paused'},
                    {'key': 'isStopped', 'value': playerState == 'stopped'},
                    {'key': 'trackName', 'value': trackName},
                    {'key': 'artist', 'value': artist},
                    {'key': 'album', 'value': album},
                    {'key': 'albumArtist', 'value': albumArtist},
                    {'key': 'trackNumber', 'value': safe_int(parts[6])},
                    {'key': 'discNumber', 'value': safe_int(parts[7])},
                    {'key': 'popularity', 'value': safe_int(parts[8])},
                    {'key': 'artworkUrl', 'value': parts[9]},
                    {'key': 'spotifyUrl', 'value': parts[11]},
                    {'key': 'trackId', 'value': parts[12]},
                    {'key': 'duration', 'value': int(duration)},
                    {'key': 'durationFormatted', 'value': self.formatTime(duration)},
                    {'key': 'playerPosition', 'value': int(position)},
                    {'key': 'playerPositionFormatted', 'value': self.formatTime(position)},
                    {'key': 'progressPercent', 'value': int((position / duration) * 100) if duration > 0 else 0},
                    {'key': 'soundVolume', 'value': volume},
                    {'key': 'muted', 'value': volume == 0},
                    {'key': 'shuffling', 'value': parts[14] == 'true'},
                    {'key': 'repeating', 'value': parts[15] == 'true'},
                ]
                if playerState == 'playing':
                    status = f"▶ {artist} - {trackName}"
                elif playerState == 'paused':
                    status = f"⏸ {artist} - {trackName}"
                else:
                    status = "⏹ Stopped"
                stateList.append({'key': 'status', 'value': status})
                stateList.extend(connectStates)
                dev.updateStatesOnServer(stateList)
                if dev.pluginProps.get('updateVariables', False):
                    self.updateVariables(dev, stateList)
                return

            if result.startswith("ERROR:"):
                self.errorLog(f"Spotify AppleScript error: {result}")
                dev.updateStateOnServer('status', value='Spotify Error')
                return

            if result.startswith("STOPPED"):
                parts = result.split("|")
                volume = safe_int(parts[1], 50) if len(parts) > 1 else 50
                shuffling = parts[2] == 'true' if len(parts) > 2 else False
                repeating = parts[3] == 'true' if len(parts) > 3 else False
                dev.updateStatesOnServer([
                    {'key': 'playerState', 'value': 'stopped'},
                    {'key': 'isPlaying', 'value': False},
                    {'key': 'isPaused', 'value': False},
                    {'key': 'isStopped', 'value': True},
                    {'key': 'trackName', 'value': ''},
                    {'key': 'artist', 'value': ''},
                    {'key': 'album', 'value': ''},
                    {'key': 'albumArtist', 'value': ''},
                    {'key': 'trackNumber', 'value': 0},
                    {'key': 'discNumber', 'value': 0},
                    {'key': 'popularity', 'value': 0},
                    {'key': 'artworkUrl', 'value': ''},
                    {'key': 'spotifyUrl', 'value': ''},
                    {'key': 'trackId', 'value': ''},
                    {'key': 'duration', 'value': 0},
                    {'key': 'durationFormatted', 'value': '00:00'},
                    {'key': 'playerPosition', 'value': 0},
                    {'key': 'playerPositionFormatted', 'value': '00:00'},
                    {'key': 'progressPercent', 'value': 0},
                    {'key': 'soundVolume', 'value': volume},
                    {'key': 'muted', 'value': volume == 0},
                    {'key': 'shuffling', 'value': shuffling},
                    {'key': 'repeating', 'value': repeating},
                    {'key': 'status', 'value': '⏹ Stopped'}
                ] + connectStates)
        except Exception as e:
            self.errorLog(f"Error updating Spotify status: {str(e)}")

    # ========================================================================
    # Spotify Connect device identification (Web API + OAuth PKCE)
    # ========================================================================

    def getConnectDeviceStates(self, dev):
        """Return fail-safe Connect states. Local playback is True only when the
        Spotify Web API confirms the active device matches the configured Mac name."""
        default = [
            {'key': 'activeDeviceName', 'value': ''},
            {'key': 'activeDeviceType', 'value': ''},
            {'key': 'activeDeviceId', 'value': ''},
            {'key': 'isLocalPlayback', 'value': False},
            {'key': 'connectStatus', 'value': 'Not authorized'},
        ]
        client_id = str(self.pluginPrefs.get('spotifyClientId', '')).strip()
        if not client_id:
            default[-1]['value'] = 'Client ID required'
            return default

        token = self.getSpotifyAccessToken()
        if not token:
            default[-1]['value'] = 'Authorization required'
            return default

        try:
            request = urllib.request.Request(
                SPOTIFY_API_BASE + '/me/player',
                headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                if response.status == 204:
                    default[-1]['value'] = 'No active player'
                    return default
                payload = json.loads(response.read().decode('utf-8'))
            device = payload.get('device') or {}
            device_name = str(device.get('name') or '')
            device_type = str(device.get('type') or '')
            device_id = str(device.get('id') or '')
            is_playing = bool(payload.get('is_playing', False))
            local_name = str(dev.pluginProps.get('localDeviceName', 'Mac Studio')).strip()
            is_local = bool(is_playing and device_name and local_name and
                            device_name.casefold() == local_name.casefold())
            return [
                {'key': 'activeDeviceName', 'value': device_name},
                {'key': 'activeDeviceType', 'value': device_type},
                {'key': 'activeDeviceId', 'value': device_id},
                {'key': 'isLocalPlayback', 'value': is_local},
                {'key': 'connectStatus', 'value': 'Playing locally' if is_local else
                 ('Playing on another device' if is_playing else 'Not playing')},
            ]
        except urllib.error.HTTPError as e:
            if e.code == 204:
                default[-1]['value'] = 'No active player'
            elif e.code == 401:
                default[-1]['value'] = 'Authorization expired'
                self.refreshSpotifyToken()
            else:
                default[-1]['value'] = 'API error {}'.format(e.code)
                self.debugLog('Spotify Connect API HTTP error: {}'.format(e.code))
            return default
        except Exception as e:
            default[-1]['value'] = 'API unavailable'
            self.debugLog('Spotify Connect API error: {}'.format(e))
            return default

    def getSpotifyAccessToken(self):
        token = str(self.pluginPrefs.get('spotifyAccessToken', '')).strip()
        expiry = float(self.pluginPrefs.get('spotifyTokenExpiry', 0) or 0)
        if token and time.time() < expiry - 60:
            return token
        return self.refreshSpotifyToken()

    def refreshSpotifyToken(self):
        refresh_token = str(self.pluginPrefs.get('spotifyRefreshToken', '')).strip()
        client_id = str(self.pluginPrefs.get('spotifyClientId', '')).strip()
        if not refresh_token or not client_id:
            return None
        try:
            body = urllib.parse.urlencode({
                'grant_type': 'refresh_token', 'refresh_token': refresh_token,
                'client_id': client_id,
            }).encode('utf-8')
            request = urllib.request.Request(SPOTIFY_TOKEN_URL, data=body,
                                             headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
            self.storeSpotifyTokens(data)
            return data.get('access_token')
        except Exception as e:
            self.debugLog('Spotify token refresh failed: {}'.format(e))
            return None

    def storeSpotifyTokens(self, data):
        self.pluginPrefs['spotifyAccessToken'] = data.get('access_token', '')
        if data.get('refresh_token'):
            self.pluginPrefs['spotifyRefreshToken'] = data['refresh_token']
        self.pluginPrefs['spotifyTokenExpiry'] = time.time() + int(data.get('expires_in', 3600))
        self.savePluginPrefs()

    def actionAuthorizeSpotify(self, pluginAction, dev):
        """Start Spotify's authorization-code-with-PKCE browser flow."""
        client_id = str(self.pluginPrefs.get('spotifyClientId', '')).strip()
        if not client_id:
            self.errorLog('Set the Spotify Client ID in Plugin Preferences before authorizing.')
            return
        if self.oauthServer:
            self.debugLog('Spotify authorization is already waiting for a browser response.')
            return
        self.oauthState = secrets.token_urlsafe(24)
        self.oauthVerifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.oauthVerifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
        query = urllib.parse.urlencode({
            'client_id': client_id, 'response_type': 'code',
            'redirect_uri': SPOTIFY_REDIRECT_URI, 'scope': SPOTIFY_SCOPE,
            'state': self.oauthState, 'code_challenge_method': 'S256',
            'code_challenge': challenge,
        })
        plugin = self

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                params = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
                if params.get('state', [''])[0] != plugin.oauthState:
                    handler.send_response(400); handler.end_headers()
                    handler.wfile.write(b'Authorization state mismatch. You can close this window.')
                    return
                code = params.get('code', [''])[0]
                if not code:
                    handler.send_response(400); handler.end_headers()
                    handler.wfile.write(b'Spotify authorization was not completed. You can close this window.')
                    return
                try:
                    body = urllib.parse.urlencode({
                        'client_id': client_id, 'grant_type': 'authorization_code',
                        'code': code, 'redirect_uri': SPOTIFY_REDIRECT_URI,
                        'code_verifier': plugin.oauthVerifier,
                    }).encode('utf-8')
                    req = urllib.request.Request(SPOTIFY_TOKEN_URL, data=body,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        token_data = json.loads(response.read().decode('utf-8'))
                    plugin.storeSpotifyTokens(token_data)
                    message = b'Spotify connected successfully. You can close this window.'
                    plugin.debugLog('Spotify Web API authorization completed.')
                except Exception as exc:
                    message = ('Spotify authorization failed: ' + str(exc)).encode('utf-8', 'replace')
                    plugin.errorLog(message.decode('utf-8', 'replace'))
                handler.send_response(200)
                handler.send_header('Content-Type', 'text/plain; charset=utf-8')
                handler.end_headers()
                handler.wfile.write(message)
                threading.Thread(target=plugin.stopOAuthServer, daemon=True).start()

            def log_message(self, format, *args):
                return

        try:
            self.oauthServer = socketserver.TCPServer(('127.0.0.1', 43821), CallbackHandler)
            self.oauthServer.allow_reuse_address = True
            threading.Thread(target=self.oauthServer.serve_forever, daemon=True).start()
            auth_url = SPOTIFY_AUTH_URL + '?' + query
            webbrowser.open(auth_url)
            self.debugLog('Opened Spotify authorization in the default browser.')
        except Exception as e:
            self.oauthServer = None
            self.errorLog('Could not start Spotify authorization callback on 127.0.0.1:43821: {}'.format(e))

    def stopOAuthServer(self):
        server = self.oauthServer
        self.oauthServer = None
        if server:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        self.oauthState = None
        self.oauthVerifier = None

    def updateVariables(self, dev, stateList):
        try:
            prefix = dev.pluginProps.get('variablePrefix', 'Spotify')
            for state in stateList:
                varName = f"{prefix}{state['key'][0].upper()}{state['key'][1:]}"
                varValue = str(state['value'])
                if varName in indigo.variables:
                    indigo.variable.updateValue(varName, value=varValue)
                else:
                    indigo.variable.create(varName, value=varValue, folder=0)
        except Exception as e:
            self.errorLog(f"Error updating variables: {str(e)}")

    def isProcessRunning(self, processName):
        try:
            result = subprocess.run(['pgrep', '-x', processName], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception:
            return False

    def executeAppleScript(self, script, timeout=APPLE_SCRIPT_TIMEOUT, waitForLock=True):
        lockAcquired = False
        try:
            if waitForLock:
                self.scriptLock.acquire()
                lockAcquired = True
            else:
                lockAcquired = self.scriptLock.acquire(False)
                if not lockAcquired:
                    return BUSY_RESULT
            process = subprocess.run(
                ['osascript', '-'], input=script, text=True, encoding='utf-8', errors='replace',
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout
            )
            if process.stderr:
                self.debugLog(f"AppleScript stderr: {process.stderr.strip()}")
            return process.stdout.strip()
        except subprocess.TimeoutExpired:
            self.errorLog(f"AppleScript timed out after {timeout} seconds")
            return None
        except Exception as e:
            self.errorLog(f"Error executing AppleScript: {str(e)}")
            return None
        finally:
            if lockAcquired:
                self.scriptLock.release()

    def formatTime(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"


    def parseActionInt(self, pluginAction, key, default=0, minimum=None, maximum=None):
        try:
            value = int(float(pluginAction.props.get(key, default)))
        except (TypeError, ValueError):
            value = default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def escapeAppleScriptString(self, value):
        return str(value).replace('\\', '\\\\').replace('"', '\\"')

    def openSpotifyUri(self, uri_or_url):
        uri = self.convertToSpotifyUri(uri_or_url)
        if not uri:
            return False
        safe_uri = self.escapeAppleScriptString(uri)
        script = f'tell application "Spotify" to activate\nopen location "{safe_uri}"'
        result = self.executeAppleScript(script)
        return result is not None

    # ========================================================================
    # Action Callback Methods
    # ========================================================================
    
    def actionPlay(self, pluginAction, dev):
        """Play action"""
        script = 'tell application "Spotify" to play'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionPause(self, pluginAction, dev):
        """Pause action"""
        script = 'tell application "Spotify" to pause'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionPlayPause(self, pluginAction, dev):
        """Play/Pause toggle action"""
        script = 'tell application "Spotify" to playpause'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionStop(self, pluginAction, dev):
        """Stop action"""
        script = 'tell application "Spotify" to pause'
        self.executeAppleScript(script)
        # Also set position to 0
        script = 'tell application "Spotify" to set player position to 0'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionNextTrack(self, pluginAction, dev):
        """Next track action"""
        script = 'tell application "Spotify" to next track'
        self.executeAppleScript(script)
        time.sleep(0.5)  # Give Spotify time to switch tracks
        self.updateSpotifyStatus(dev)
        
    def actionPreviousTrack(self, pluginAction, dev):
        """Previous track action"""
        script = 'tell application "Spotify" to previous track'
        self.executeAppleScript(script)
        time.sleep(0.5)  # Give Spotify time to switch tracks
        self.updateSpotifyStatus(dev)
        
    def actionSetVolume(self, pluginAction, dev):
        """Set volume action"""
        volume = self.parseActionInt(pluginAction, 'volume', default=50, minimum=0, maximum=100)
        script = f'tell application "Spotify" to set sound volume to {volume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionVolumeUp(self, pluginAction, dev):
        """Volume up action"""
        amount = self.parseActionInt(pluginAction, 'amount', default=10, minimum=0, maximum=100)
        currentVolume = int(dev.states.get('soundVolume', 50))
        newVolume = min(100, currentVolume + amount)
        script = f'tell application "Spotify" to set sound volume to {newVolume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionVolumeDown(self, pluginAction, dev):
        """Volume down action"""
        amount = self.parseActionInt(pluginAction, 'amount', default=10, minimum=0, maximum=100)
        currentVolume = int(dev.states.get('soundVolume', 50))
        newVolume = max(0, currentVolume - amount)
        script = f'tell application "Spotify" to set sound volume to {newVolume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionMute(self, pluginAction, dev):
        """Mute action"""
        devInfo = self.deviceDict.get(dev.id)
        if devInfo:
            # Store current volume
            currentVolume = int(dev.states.get('soundVolume', 50))
            devInfo['previousVolume'] = currentVolume
        script = 'tell application "Spotify" to set sound volume to 0'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionUnmute(self, pluginAction, dev):
        """Unmute action"""
        devInfo = self.deviceDict.get(dev.id)
        previousVolume = 50  # Default
        if devInfo and devInfo.get('previousVolume'):
            previousVolume = devInfo['previousVolume']
        script = f'tell application "Spotify" to set sound volume to {previousVolume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSetPosition(self, pluginAction, dev):
        """Set playback position action"""
        position = self.parseActionInt(pluginAction, 'position', default=0, minimum=0)
        script = f'tell application "Spotify" to set player position to {position}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSkipForward(self, pluginAction, dev):
        """Skip forward action"""
        seconds = self.parseActionInt(pluginAction, 'seconds', default=10, minimum=0)
        currentPos = int(dev.states.get('playerPosition', 0))
        newPos = currentPos + seconds
        script = f'tell application "Spotify" to set player position to {newPos}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSkipBackward(self, pluginAction, dev):
        """Skip backward action"""
        seconds = self.parseActionInt(pluginAction, 'seconds', default=10, minimum=0)
        currentPos = int(dev.states.get('playerPosition', 0))
        newPos = max(0, currentPos - seconds)
        script = f'tell application "Spotify" to set player position to {newPos}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSetShuffle(self, pluginAction, dev):
        """Set shuffle action"""
        shuffleState = pluginAction.props.get('shuffleState', 'toggle')
        
        if shuffleState == 'toggle':
            currentShuffle = dev.states.get('shuffling', False)
            shuffleState = 'off' if currentShuffle else 'on'
        
        shuffleBool = 'true' if shuffleState == 'on' else 'false'
        script = f'tell application "Spotify" to set shuffling to {shuffleBool}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSetRepeat(self, pluginAction, dev):
        """Set repeat action"""
        repeatState = pluginAction.props.get('repeatState', 'toggle')
        
        if repeatState == 'toggle':
            currentRepeat = dev.states.get('repeating', False)
            repeatState = 'off' if currentRepeat else 'on'
        
        repeatBool = 'true' if repeatState == 'on' else 'false'
        script = f'tell application "Spotify" to set repeating to {repeatBool}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionPlayTrack(self, pluginAction, dev):
        """Play specific track action"""
        trackUri = pluginAction.props.get('trackUri', '')
        if trackUri:
            if self.openSpotifyUri(trackUri):
                time.sleep(0.5)
                self.updateSpotifyStatus(dev)

    def actionPlayPlaylist(self, pluginAction, dev):
        """Play playlist action"""
        playlistUri = pluginAction.props.get('playlistUri', '')
        if playlistUri:
            if self.openSpotifyUri(playlistUri):
                time.sleep(0.5)
                self.updateSpotifyStatus(dev)

    def actionPlayAlbum(self, pluginAction, dev):
        """Play album action"""
        albumUri = pluginAction.props.get('albumUri', '')
        if albumUri:
            if self.openSpotifyUri(albumUri):
                time.sleep(0.5)
                self.updateSpotifyStatus(dev)

    def actionPlayArtist(self, pluginAction, dev):
        """Play artist action"""
        artistUri = pluginAction.props.get('artistUri', '')
        if artistUri:
            if self.openSpotifyUri(artistUri):
                time.sleep(0.5)
                self.updateSpotifyStatus(dev)

    def actionSearchAndPlay(self, pluginAction, dev):
        """Search and play action"""
        searchQuery = pluginAction.props.get('searchQuery', '').strip()
        searchType = pluginAction.props.get('searchType', 'track').strip()
        if searchQuery:
            query = searchQuery.replace(' ', '+')
            searchUri = f'spotify:search:{searchType}:{query}' if searchType else f'spotify:search:{query}'
            if self.openSpotifyUri(searchUri):
                time.sleep(0.5)
                self.updateSpotifyStatus(dev)

    def actionUpdateNow(self, pluginAction, dev):
        """Force immediate update"""
        self.updateSpotifyStatus(dev)
        
    def convertToSpotifyUri(self, uri_or_url):
        """Convert Spotify URL to URI format"""
        if uri_or_url.startswith('spotify:'):
            return uri_or_url
        elif 'open.spotify.com' in uri_or_url:
            # Extract the type and ID from URL
            # Format: https://open.spotify.com/track/1234567890
            match = re.search(r'spotify\.com/(track|album|artist|playlist)/([a-zA-Z0-9]+)', uri_or_url)
            if match:
                content_type = match.group(1)
                content_id = match.group(2)
                return f'spotify:{content_type}:{content_id}'
        return uri_or_url
