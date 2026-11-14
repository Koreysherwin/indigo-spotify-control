Spotify Control 1.0.8 — Spotify Connect device detection

WHAT CHANGED
- Added Spotify Web API active-device detection using OAuth Authorization Code + PKCE.
- Added Indigo states: activeDeviceName, activeDeviceType, activeDeviceId,
  isLocalPlayback, and connectStatus.
- Added a per-device setting for the Mac's Spotify Connect device name
  (default: Mac Studio).
- Existing AppleScript playback controls and legacy states are retained.
- isLocalPlayback is fail-safe: it remains False unless the Web API confirms
  that Spotify is currently playing on the configured device.

ONE-TIME SETUP
1. Go to https://developer.spotify.com/dashboard and create a Spotify app.
2. In the app settings, add this Redirect URI exactly:
   http://127.0.0.1:43821/callback
3. Copy the app's Client ID.
4. In Indigo, open Spotify Control Plugin Preferences and paste the Client ID
   into “Spotify Developer App Client ID”. Save the preferences.
5. On the Spotify Player device, set “Local Spotify Connect device name” to
   the exact device name shown by Spotify Connect on the Mac (default Mac Studio).
6. Run the device action “Authorize Spotify Connect Detection”. A browser will
   open; sign in to Spotify and approve the requested playback-state permission.
7. Return to Indigo. The device states should populate on the next poll.

AUTOMATION CHANGE
For speaker power-on automations, use the new isLocalPlayback state (True),
not the legacy isPlaying state. The legacy isPlaying state is deliberately
preserved for compatibility and may still reflect remote Spotify Connect
playback as exposed by the local Spotify application.

CONNECT STATUS VALUES
- Playing locally
- Playing on another device
- Not playing
- No active player
- Authorization required / expired
- Client ID required
- API unavailable / API error <code>

NOTES
- The Mac running Indigo must be able to reach Spotify's API and open the
  local callback port 43821 on 127.0.0.1 during authorization.
- Spotify API access is subject to Spotify developer-app/account policies.
- If the Mac's Spotify Connect name changes, update the device setting.
