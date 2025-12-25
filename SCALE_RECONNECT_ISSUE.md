# WebSerial Scale Reconnection Issue

## The Problem
After disconnecting or refreshing the POS terminal page, the scale cannot reconnect. Chrome throws:
```
"Failed to execute 'open' on 'SerialPort': Failed to open serial port"
```

**Key observation:** The scale-test page works perfectly - even after disconnect or refresh, it can reconnect without unplugging USB.

## Root Cause Analysis
The issue is that **stale port objects or reader locks** prevent Chrome from opening the serial port. Even with cleanup attempts, something is holding the port in a bad state.

## Things Tried (All Failed)

1. **Added `cleanupScaleConnection()` before reconnect** - Calls `disconnect()` to release reader locks before attempting reconnect

2. **Fixed `disconnect()` to use proper cleanup** - Uses `reader.cancel()`, `reader.releaseLock()`, then `port.close()`

3. **Added port state check** - Check `if (!port.readable)` before calling `open()` to avoid opening already-open ports

4. **Aggressive port cleanup** - If port has readable stream, get a temp reader, cancel it, release lock, close port, wait 100ms, then open

5. **Cleanup before creating new ScaleReader** - Both `tryAutoReconnect()` and `testScaleConnection()` now cleanup existing `state.scaleReader` before creating new instance

6. **Skip `getPorts()` entirely** - Changed `handleScaleReconnect()` to skip `tryAutoReconnect()` (which uses `getPorts()`) and go directly to `testScaleConnection()` (which uses `requestPort()` for fresh port reference)

## Key Difference: scale-test vs terminal.html

**scale-test works because:**
- Creates fresh `ScaleReader()` each time (line 767)
- Uses `autoDetect()` which handles port internally
- Simpler flow, no state management complexity

**terminal.html fails because:**
- Complex state management with `state.scaleReader`
- Multiple code paths that create/reuse ScaleReader instances
- Possibly orphaned readers or port references somewhere

## Files Modified
- `scrap_metal_suite/www/pos/terminal.html` - Reconnect flow, cleanup logic
- `scrap_metal_suite/public/js/pos-translations.js` - Added `selectPortToReconnect` translation

## Next Steps to Investigate

1. **Compare scale-test flow exactly** - The `autoDetect()` method in ScaleReader might handle port acquisition differently than `testScaleConnection()`

2. **Check if multiple browser tabs** are holding the port - Close all other tabs accessing the scale

3. **Add extensive logging** to track exactly when readers are acquired vs released

4. **Consider using `autoDetect()` in terminal.html** instead of manual port open - This is what scale-test uses successfully

5. **Check `checkSessionScale()` on page load** (line ~4594) - This calls `tryAutoReconnect()` on page load and might be leaving stale state

6. **Investigate if the port permission itself is the issue** - Try `port.forget()` to completely release permission, then re-authorize

## Code Locations
| Function | File | Line |
|----------|------|------|
| `handleScaleReconnect()` | terminal.html | ~2345 |
| `tryAutoReconnect()` | terminal.html | ~693 |
| `testScaleConnection()` | terminal.html | ~2085 |
| `cleanupScaleConnection()` | terminal.html | ~674 |
| `ScaleReader.disconnect()` | scale_reader.js | ~562 |
| `ScaleReader.autoDetect()` | scale_reader.js | ~80 |

## Recommended Next Action
**Try using `autoDetect()` in terminal.html** - since this is exactly what scale-test uses and it works. The `testScaleConnection()` function manually opens ports which may be handled differently than `autoDetect()`.
