#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spotify Control Plugin for Indigo
Provides comprehensive control and monitoring of Spotify playback
"""

import indigo
import time
import subprocess
import json
import re

# Constants
kUpdateFrequencyKey = "updateFrequency"


class Plugin(indigo.PluginBase):
    """Main plugin class for Spotify control"""
    
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.deviceDict = {}
        
    def startup(self):
        """Called when plugin starts"""
        self.debugLog(u"Spotify Plugin startup called")
        
    def shutdown(self):
        """Called when plugin shuts down"""
        self.debugLog(u"Spotify Plugin shutdown called")
        
    def deviceStartComm(self, dev):
        """Called when device communication starts"""
        self.debugLog(u"Starting device: " + dev.name)
        
        # Initialize the device's update frequency
        updateFreq = float(dev.pluginProps.get(kUpdateFrequencyKey, 1))
        
        # Store device info
        self.deviceDict[dev.id] = {
            'device': dev,
            'updateFrequency': updateFreq,
            'lastUpdate': 0,
            'previousVolume': None  # For mute/unmute
        }
        
        # Do initial update
        self.updateSpotifyStatus(dev)
        
    def deviceStopComm(self, dev):
        """Called when device communication stops"""
        self.debugLog(u"Stopping device: " + dev.name)
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]
            
    def runConcurrentThread(self):
        """Main plugin loop - updates device states"""
        try:
            while True:
                currentTime = time.time()
                
                for devId, devInfo in list(self.deviceDict.items()):
                    dev = devInfo['device']
                    updateFreq = devInfo['updateFrequency']
                    lastUpdate = devInfo['lastUpdate']
                    
                    # Check if it's time to update this device
                    if currentTime - lastUpdate >= updateFreq:
                        self.updateSpotifyStatus(dev)
                        devInfo['lastUpdate'] = currentTime
                
                self.sleep(0.1)  # Short sleep to prevent CPU spinning
                
        except self.StopThread:
            pass
            
    def updateSpotifyStatus(self, dev):
        """Update all Spotify status information"""
        try:
            # Build comprehensive AppleScript to get all Spotify data
            script = '''
            tell application "System Events"
                set spotifyRunning to (name of processes) contains "Spotify"
            end tell
            
            if spotifyRunning then
                tell application "Spotify"
                    try
                        set playerState to player state as string
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
                            set soundVol to sound volume
                            set isShuffling to shuffling
                            set isRepeating to repeating
                            
                            -- Replace pipe characters to avoid delimiter conflicts
                            set trackName to my replaceText(trackName, "|", "§")
                            set trackArtist to my replaceText(trackArtist, "|", "§")
                            set trackAlbum to my replaceText(trackAlbum, "|", "§")
                            set albumArtist to my replaceText(albumArtist, "|", "§")
                            
                            return "SUCCESS:" & playerState & "|" & trackName & "|" & trackArtist & "|" & trackAlbum & "|" & trackDuration & "|" & playerPos & "|" & trackNumber & "|" & discNumber & "|" & trackPopularity & "|" & artworkUrl & "|" & albumArtist & "|" & spotifyUrl & "|" & trackId & "|" & soundVol & "|" & isShuffling & "|" & isRepeating
                        else
                            return "STOPPED"
                        end if
                    on error errMsg
                        return "ERROR:" & errMsg
                    end try
                end tell
            else
                return "NOTRUNNING"
            end if
            
            on replaceText(theText, oldString, newString)
                set AppleScript's text item delimiters to oldString
                set textItems to text items of theText
                set AppleScript's text item delimiters to newString
                set theText to textItems as string
                set AppleScript's text item delimiters to ""
                return theText
            end replaceText
            '''
            
            # Execute AppleScript
            result = self.executeAppleScript(script)
            
            if result and result.startswith("SUCCESS:"):
                # Parse the pipe-delimited result
                parts = result[8:].split("|")  # Remove "SUCCESS:" prefix
                
                if len(parts) >= 16:
                    stateList = []
                    
                    # Player state
                    playerState = parts[0]
                    stateList.append({'key': 'playerState', 'value': playerState})
                    stateList.append({'key': 'isPlaying', 'value': playerState == 'playing'})
                    stateList.append({'key': 'isPaused', 'value': playerState == 'paused'})
                    stateList.append({'key': 'isStopped', 'value': playerState == 'stopped'})
                    
                    # Track information
                    trackName = parts[1].replace("§", "|")
                    artist = parts[2].replace("§", "|")
                    album = parts[3].replace("§", "|")
                    albumArtist = parts[10].replace("§", "|")
                    
                    stateList.append({'key': 'trackName', 'value': trackName})
                    stateList.append({'key': 'artist', 'value': artist})
                    stateList.append({'key': 'album', 'value': album})
                    stateList.append({'key': 'albumArtist', 'value': albumArtist})
                    
                    # Track numbers and metadata - handle floats from AppleScript
                    stateList.append({'key': 'trackNumber', 'value': int(float(parts[6]))})
                    stateList.append({'key': 'discNumber', 'value': int(float(parts[7]))})
                    stateList.append({'key': 'popularity', 'value': int(float(parts[8]))})
                    
                    # URLs and IDs
                    stateList.append({'key': 'artworkUrl', 'value': parts[9]})
                    stateList.append({'key': 'spotifyUrl', 'value': parts[11]})
                    stateList.append({'key': 'trackId', 'value': parts[12]})
                    
                    # Duration and position
                    duration = float(parts[4]) / 1000.0  # Convert ms to seconds
                    position = float(parts[5])
                    
                    stateList.append({'key': 'duration', 'value': int(duration)})
                    stateList.append({'key': 'durationFormatted', 'value': self.formatTime(duration)})
                    stateList.append({'key': 'playerPosition', 'value': int(position)})
                    stateList.append({'key': 'playerPositionFormatted', 'value': self.formatTime(position)})
                    
                    # Progress percentage
                    progressPercent = 0
                    if duration > 0:
                        progressPercent = int((position / duration) * 100)
                    stateList.append({'key': 'progressPercent', 'value': progressPercent})
                    
                    # Volume
                    volume = int(float(parts[13]))
                    stateList.append({'key': 'soundVolume', 'value': volume})
                    stateList.append({'key': 'muted', 'value': volume == 0})
                    
                    # Shuffle and repeat
                    stateList.append({'key': 'shuffling', 'value': parts[14] == 'true'})
                    stateList.append({'key': 'repeating', 'value': parts[15] == 'true'})
                    
                    # Status display
                    if playerState == 'playing':
                        status = f"▶ {artist} - {trackName}"
                    elif playerState == 'paused':
                        status = f"⏸ {artist} - {trackName}"
                    else:
                        status = "⏹ Stopped"
                    stateList.append({'key': 'status', 'value': status})
                    
                    # Update all states
                    dev.updateStatesOnServer(stateList)
                    
                    # Update variables if enabled
                    if dev.pluginProps.get('updateVariables', False):
                        self.updateVariables(dev, stateList)
            else:
                # Spotify not responding, stopped, or error
                stateList = [
                    {'key': 'playerState', 'value': 'stopped'},
                    {'key': 'isPlaying', 'value': False},
                    {'key': 'isPaused', 'value': False},
                    {'key': 'isStopped', 'value': True},
                    {'key': 'status', 'value': 'Not Running' if result == 'NOTRUNNING' else 'Stopped'}
                ]
                dev.updateStatesOnServer(stateList)
                
        except Exception as e:
            self.errorLog(f"Error updating Spotify status: {str(e)}")
            
    def updateVariables(self, dev, stateList):
        """Update Indigo variables with Spotify data"""
        try:
            prefix = dev.pluginProps.get('variablePrefix', 'Spotify')
            
            # Create or update variables for each state
            for state in stateList:
                varName = f"{prefix}{state['key'][0].upper()}{state['key'][1:]}"
                varValue = str(state['value'])
                
                # Check if variable exists
                if varName in indigo.variables:
                    indigo.variable.updateValue(varName, value=varValue)
                else:
                    # Create new variable
                    indigo.variable.create(varName, value=varValue, folder=0)
                    
        except Exception as e:
            self.errorLog(f"Error updating variables: {str(e)}")
            
    def executeAppleScript(self, script):
        """Execute AppleScript and return results as string"""
        try:
            # Use osascript to execute the script
            process = subprocess.Popen(
                ['osascript', '-e', script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if stderr:
                self.debugLog(f"AppleScript stderr: {stderr.decode('utf-8')}")
                
            # Return the output string
            output = stdout.decode('utf-8').strip()
            return output
            
        except Exception as e:
            self.errorLog(f"Error executing AppleScript: {str(e)}")
            return None
            
    def formatTime(self, seconds):
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
        
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
        volume = int(pluginAction.props.get('volume', 50))
        volume = max(0, min(100, volume))  # Clamp between 0-100
        script = f'tell application "Spotify" to set sound volume to {volume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionVolumeUp(self, pluginAction, dev):
        """Volume up action"""
        amount = int(pluginAction.props.get('amount', 10))
        currentVolume = int(dev.states.get('soundVolume', 50))
        newVolume = min(100, currentVolume + amount)
        script = f'tell application "Spotify" to set sound volume to {newVolume}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionVolumeDown(self, pluginAction, dev):
        """Volume down action"""
        amount = int(pluginAction.props.get('amount', 10))
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
        position = int(pluginAction.props.get('position', 0))
        script = f'tell application "Spotify" to set player position to {position}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSkipForward(self, pluginAction, dev):
        """Skip forward action"""
        seconds = int(pluginAction.props.get('seconds', 10))
        currentPos = int(dev.states.get('playerPosition', 0))
        newPos = currentPos + seconds
        script = f'tell application "Spotify" to set player position to {newPos}'
        self.executeAppleScript(script)
        self.updateSpotifyStatus(dev)
        
    def actionSkipBackward(self, pluginAction, dev):
        """Skip backward action"""
        seconds = int(pluginAction.props.get('seconds', 10))
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
            # Convert URL to URI if needed
            trackUri = self.convertToSpotifyUri(trackUri)
            script = f'tell application "Spotify" to play track "{trackUri}"'
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateSpotifyStatus(dev)
        
    def actionPlayPlaylist(self, pluginAction, dev):
        """Play playlist action"""
        playlistUri = pluginAction.props.get('playlistUri', '')
        if playlistUri:
            playlistUri = self.convertToSpotifyUri(playlistUri)
            script = f'tell application "Spotify" to play track "{playlistUri}"'
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateSpotifyStatus(dev)
        
    def actionPlayAlbum(self, pluginAction, dev):
        """Play album action"""
        albumUri = pluginAction.props.get('albumUri', '')
        if albumUri:
            albumUri = self.convertToSpotifyUri(albumUri)
            script = f'tell application "Spotify" to play track "{albumUri}"'
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateSpotifyStatus(dev)
        
    def actionPlayArtist(self, pluginAction, dev):
        """Play artist action"""
        artistUri = pluginAction.props.get('artistUri', '')
        if artistUri:
            artistUri = self.convertToSpotifyUri(artistUri)
            script = f'tell application "Spotify" to play track "{artistUri}"'
            self.executeAppleScript(script)
            time.sleep(0.5)
            self.updateSpotifyStatus(dev)
        
    def actionSearchAndPlay(self, pluginAction, dev):
        """Search and play action"""
        searchQuery = pluginAction.props.get('searchQuery', '')
        if searchQuery:
            # Use Spotify's search URI format
            searchUri = f'spotify:search:{searchQuery.replace(" ", "+")}'
            script = f'tell application "Spotify" to play track "{searchUri}"'
            self.executeAppleScript(script)
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
