# Changelog

## Version 1.0.6
- Corrected the Indigo-visible plugin version so `PluginVersion` matches the updated release instead of still showing `1.0.3`.
- Packaged a corrected bundle for testing.

## Version 1.0.5
- Fixed Unicode decoding errors when Spotify track metadata contains non-ASCII characters.
- Updated AppleScript subprocess handling to use UTF-8-safe decoding.

## Version 1.0.4
- Replaced a non-ASCII placeholder character in the AppleScript path with an ASCII-safe token.
- Resolved errors like: `ascii' codec can't encode character '\xa7'`.

## Version 1.0.3
- Added serialized AppleScript execution so overlapping calls cannot pile up.
- Added AppleScript timeouts to reduce the chance of hung polling calls.
- Removed `System Events` process checks from the normal polling path.
- Increased the default polling interval to 5 seconds.
- Enforced a 2-second minimum polling interval in code.
- Reduced the risk of GUI/session instability caused by aggressive AppleScript polling.

## [1.0.0] - 2025-01-09

### Added
- Initial release
- Complete playback control (play, pause, stop, next, previous)
- Volume control with mute/unmute
- Position seeking (jump to time, skip forward/backward)
- Shuffle and repeat controls
- Play by Spotify URI/URL (tracks, playlists, albums, artists)
- Search and play functionality
- Real-time track information monitoring
- Track popularity and artwork URL tracking
- Comprehensive state monitoring
- Variable integration for Control Pages
