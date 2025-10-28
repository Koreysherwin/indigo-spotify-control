# Spotify Control Plugin for Indigo

A comprehensive Indigo plugin for controlling Spotify and monitoring all playback data in real-time.

## Features

### Device States (Auto-Updated)
The plugin tracks and updates the following Spotify information:

#### Playback Status
- **Player State**: playing, paused, or stopped
- **Is Playing**: Boolean indicator
- **Is Paused**: Boolean indicator  
- **Is Stopped**: Boolean indicator

#### Track Information
- **Track Name**: Current track title
- **Artist**: Track artist(s)
- **Album**: Album name
- **Album Artist**: Album artist
- **Track Number**: Track number on album
- **Disc Number**: Disc number for multi-disc albums
- **Spotify URL**: Direct Spotify link
- **Track ID**: Unique Spotify track ID
- **Artwork URL**: Album artwork image URL
- **Popularity**: Track popularity (0-100)
- **Release Date**: Track/album release date

#### Playback Position
- **Player Position**: Current position in seconds
- **Player Position (Formatted)**: Position as MM:SS
- **Duration**: Track length in seconds
- **Duration (Formatted)**: Duration as MM:SS
- **Progress Percentage**: Playback progress (0-100%)

#### Audio Settings
- **Volume**: Current volume (0-100)
- **Muted**: Boolean mute status
- **Shuffling**: Shuffle mode on/off
- **Repeating**: Repeat mode on/off

#### Display
- **Status**: Human-readable status (e.g., "▶ Artist - Track Name")

### Actions

#### Playback Control
- **Play**: Start playback
- **Pause**: Pause playback
- **Play/Pause Toggle**: Toggle between play and pause
- **Stop**: Stop playback and reset position
- **Next Track**: Skip to next track
- **Previous Track**: Go to previous track

#### Volume Control
- **Set Volume**: Set specific volume level (0-100)
- **Volume Up**: Increase volume by specified amount
- **Volume Down**: Decrease volume by specified amount
- **Mute**: Mute audio (remembers previous volume)
- **Unmute**: Restore previous volume

#### Position Control
- **Set Playback Position**: Jump to specific second in track
- **Skip Forward**: Jump forward by seconds
- **Skip Backward**: Jump backward by seconds

#### Playback Options
- **Set Shuffle**: Turn shuffle on, off, or toggle
- **Set Repeat**: Turn repeat on, off, or toggle

#### Content Selection
- **Play Specific Track**: Play by Spotify URI or URL
- **Play Playlist**: Play entire playlist
- **Play Album**: Play entire album
- **Play Artist**: Play artist's top tracks
- **Search and Play**: Search Spotify and play first result

#### Utility
- **Update Now**: Force immediate status update

## Installation

1. **Download** the `Spotify.indigoPlugin` package
2. **Double-click** the plugin file to install in Indigo
3. **Restart** the Indigo server if prompted

## Setup

### Creating a Spotify Device

1. In Indigo, go to **Devices** → **New...**
2. Set Type: **Plugin** → **Spotify Control**
3. Select Model: **Spotify Player**
4. Configure settings:
   - **Update Frequency**: How often to poll Spotify (0.5-10 seconds)
   - **Update Indigo Variables**: Enable to create/update variables
   - **Variable Prefix**: Prefix for variable names (default: "Spotify")

### Device Settings

#### Update Frequency
Choose how often the plugin checks Spotify status:
- **0.5 seconds**: Smoothest updates, higher CPU usage
- **1 second**: Recommended for most uses
- **2-5 seconds**: Good for background monitoring
- **10 seconds**: Minimal CPU usage

#### Variable Updates
If enabled, the plugin will create and update Indigo variables with all Spotify data:
- Variables are named: `{Prefix}{StateName}` (e.g., `SpotifyTrackName`)
- Useful for Control Pages and other integrations
- Variables are created automatically if they don't exist

## Usage Examples

### Basic Playback Control
```applescript
-- In Indigo Actions
Execute Action "Spotify Player - Play"
Execute Action "Spotify Player - Pause"
Execute Action "Spotify Player - Next Track"
```

### Volume Control
```applescript
-- Set volume to 50%
Execute Action "Spotify Player - Set Volume" with value "50"

-- Increase volume by 10
Execute Action "Spotify Player - Volume Up" with value "10"

-- Mute/Unmute
Execute Action "Spotify Player - Mute"
Execute Action "Spotify Player - Unmute"
```

### Play Specific Content
```applescript
-- Play a specific track
Execute Action "Spotify Player - Play Specific Track"
  Track URI: "spotify:track:3n3Ppam7vgaVa1iaRUc9Lp"

-- Play a playlist
Execute Action "Spotify Player - Play Playlist"
  Playlist URI: "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"

-- Search and play
Execute Action "Spotify Player - Search and Play"
  Search Query: "Bohemian Rhapsody Queen"
  Search Type: "Track"
```

### Triggers Based on Spotify State

Create triggers based on device state changes:
- Trigger when playback starts: `isPlaying` becomes `true`
- Trigger when specific artist plays: `artist` contains "The Beatles"
- Trigger when volume changes: `soundVolume` changes
- Trigger when shuffle enabled: `shuffling` becomes `true`

### Control Page Examples

Add Spotify controls to your Control Pages:
- Display current track: Use `status` state
- Show album art: Use `artworkUrl` state  
- Display progress: Use `playerPositionFormatted` and `durationFormatted`
- Volume slider: Control via Set Volume action
- Play/Pause button: Use Play/Pause Toggle action

### Spotify URIs and URLs

The plugin accepts both Spotify URIs and URLs:

**URI Format** (preferred):
```
spotify:track:3n3Ppam7vgaVa1iaRUc9Lp
spotify:album:6QaVfG1pHYl1z15ZxkvVDW
spotify:artist:3WrFJ7ztbogyGnTHbHJFl2
spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
```

**URL Format** (automatically converted):
```
https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp
https://open.spotify.com/album/6QaVfG1pHYl1z15ZxkvVDW
https://open.spotify.com/artist/3WrFJ7ztbogyGnTHbHJFl2
https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
```

To get URIs/URLs:
1. Right-click any item in Spotify
2. Select **Share** → **Copy Spotify URI** (or Copy Link)
3. Paste into plugin action

## Scripting Examples

### Python Script
```python
# Get current track info
spotify_dev = indigo.devices[12345]  # Your device ID
track = spotify_dev.states['trackName']
artist = spotify_dev.states['artist']
indigo.server.log(f"Now playing: {artist} - {track}")

# Control playback
indigo.device.execute("Spotify Player", action="play")
indigo.device.execute("Spotify Player", action="nextTrack")
```

### AppleScript
```applescript
tell application "IndigoServer"
    -- Get current track
    set trackName to value of variable "SpotifyTrackName"
    
    -- Execute actions
    execute action "Play/Pause Toggle" of device "Spotify Player"
end tell
```

## Troubleshooting

### Plugin Not Updating
- Ensure Spotify desktop app is running
- Check that Update Frequency is set appropriately
- Try "Update Now" action to force refresh
- Check Indigo log for errors

### Actions Not Working
- Verify Spotify desktop app is running and responsive
- Some actions require active playback
- Check that Spotify has proper macOS permissions
- Try controlling Spotify directly to verify it's working

### Variables Not Created
- Enable "Update Indigo Variables" in device settings
- Check variable prefix doesn't conflict with existing variables
- Variables are created on first update after enabling

### Spotify Not Responding
The plugin uses AppleScript to communicate with Spotify:
- Spotify must be the desktop app (not web player)
- macOS may prompt for accessibility permissions
- Grant permissions in System Preferences → Security & Privacy

## Technical Details

### Requirements
- Indigo 2022.1 or later
- macOS with Spotify desktop app installed
- Python 3.7+ (included with Indigo)

### How It Works
- Uses AppleScript to communicate with Spotify application
- Polls Spotify at configurable intervals
- No network requests required (all local)
- No Spotify API credentials needed

### Performance
- Minimal CPU usage with 1-2 second update frequency
- No impact on Spotify performance
- Updates only when device is active in Indigo

## Version History

### 1.0.0 (Current)
- Initial release
- Complete playback control
- Comprehensive state monitoring
- Variable integration
- All Spotify data available

## Support

For issues or feature requests:
1. Check Indigo plugin log for errors
2. Verify Spotify desktop app is working
3. Test with different update frequencies
4. Report issues with log excerpts

## License

This plugin is provided as-is for use with Indigo home automation.

---

**Note**: This plugin controls the Spotify desktop application on the Mac running Indigo. It does not control Spotify Connect devices or other Spotify instances. For multi-room control, use Spotify Connect within the Spotify app itself.
