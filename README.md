# DJI Avata OSD Overlay Tool

Burn DJI telemetry OSD (On-Screen Display) overlays onto your drone footage with a powerful GUI editor. Supports multi-flight detection, per-element positioning, overlay delay compensation, and quality re-encoding.

**Works on Windows, Linux, and other platforms**

![OSD Preview](docs/osd-preview.png)

## Features

✨ **Core Features**
- **Multi-flight Detection** - Automatically detect individual recording sessions from CSV telemetry
- **Visual OSD Editor** - Drag-and-drop layout editor with real-time preview
- **Per-Element Toggle** - Show/hide individual OSD elements (speed, altitude, GPS, battery, etc.)
- **Offset & Size Adjustment** - Pixel-perfect positioning for each element
- **Global Scaling** - Scale all OSD elements proportionally (0.25x - 3.0x)
- **17 OSD Elements** - Flight mode, speed, altitude, compass, crosshair, GPS, battery, and more
- **Auto-save Settings** - Persistent configuration saved to `~/.dji_osd_tool/osd_settings.json`
- **Overlay Delay** - Synchronize telemetry with video by adjusting delay (±120 seconds)
- **Quality Reducer** - Re-encode videos with H.264 compression and resolution scaling
- **Cross-Platform** - Linux and Windows supported

## Quick Start

### Installation

**Option 1: From PyPI (Recommended)**
```bash
pip install dji-osd-tool
dji-osd-tool  # Launch GUI
```

**Option 2: From Source**
```bash
git clone https://github.com/Devsur11/dji-osd-tool.git
cd dji-osd-tool
pip install -r requirements.txt
python dji_osd_tool.py
```

**Option 3: Standalone Executable**
Download the latest release from [GitHub Releases](https://github.com/Devsur11/dji-osd-tool/releases):
- Linux: `dji-osd-tool-linux-x64.tar.gz`
- Windows: `dji-osd-tool-windows-x64.exe`

### System Requirements

- **Python**: 3.8 or higher
- **OS**: Windows, Linux (macOS discouraged - no GPU support)
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB free (for video processing)
- **GUI**: X11 or Wayland (Linux), native Windows (Windows)

**Optional**: Install FFmpeg for best video re-encoding quality
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (with Chocolatey)
choco install ffmpeg

# macOS (Homebrew)
brew install ffmpeg
```

## Usage Guide

### Step 1: Load Telemetry CSV
```
1. Click "Open Telemetry CSV" in the top bar
2. Select your telemetry CSV file (exported from SquirrelCast FPV app)
3. The tool automatically detects individual flights and displays them in the left panel
```

### Step 2: Select a Flight
```
1. Click a flight card to select it
2. View flight statistics (duration, altitude, speed, battery)
3. Flight 1 is selected automatically
```

### Step 3: Choose a Video File
```
1. Under the Overlay tab, click "Browse" next to "Video File"
2. Select your corresponding DJI video clip
3. Sync Verification shows green/yellow/red status:
   - Green: Perfect sync (< 2s difference)
   - Yellow: Acceptable (< 5s difference)
   - Red: Large mismatch (> 5s) - check your file!
```

### Step 4: Adjust Overlay Delay (Optional)
Use this to fix timing mismatches between telemetry and video:
```
- Positive value (+N s): Telemetry appears too early in video
  → Use positive delay to shift OSD forward in time

- Negative value (−N s): Telemetry lags behind video
  → Use negative delay to shift OSD backward in time

- Accept decimal values (1.5, −0.3, etc.)
```

### Step 5: Edit OSD Layout
```
1. Click "OSD Editor" in the top-right corner
2. Drag elements to reposition them on the 640×360 canvas
3. Toggle checkboxes to show/hide elements
4. Adjust X/Y offset and size in the detail panel
5. Use Global OSD Scale slider to resize all elements
6. Click "Save & Close" when done
```

### Step 6: Generate the Overlay
```
1. Set output file path (auto-suggested)
2. Click "Generate OSD Overlay"
3. Monitor progress in the log below
4. Output is an MP4 file with OSD burned into every frame
```

### Step 7: Optional - Re-encode for Sharing
Use the Quality Reducer tab to compress video:
```
1. Select resolution preset (original, 1080p, 720p, 480p, 360p)
2. Choose quality preset (Ultra, High, Medium, Low, Tiny)
3. Set input/output files
4. Click "Compress / Re-encode"
5. For YouTube: Use Medium quality at 720p or 1080p
```

## OSD Elements Reference

### 17 Customizable Elements

| Element | Description | Location |
|---------|-------------|----------|
| **Flight Mode Box** | Displays current flight mode (N/S/M) | Bottom Left |
| **V-Speed & Altitude** | Vertical speed and relative altitude | Bottom Left |
| **H-Speed & Distance** | Horizontal speed and distance from home | Bottom Left |
| **Artificial Horizon** | Visual pitch/roll indicator | Center |
| **Centre Crosshair** | Center point indicator | Center |
| **Compass & Heading** | Heading indicator with direction | Top Center |
| **Speed Tape** | Scrolling speed scale | Left Side |
| **Pitch/Roll Labels** | Pitch and roll angle text | Left Side |
| **Altitude Tape** | Scrolling altitude scale | Right Side |
| **GPS Satellite Count** | Number of locked GPS satellites with icon | Top Right |
| **GPS Coordinates** | Latitude and longitude display | Bottom Right |
| **RC/HD Signal Bars** | Signal strength indicators | Bottom Right |
| **Battery Indicator** | Battery percentage with fill bar | Bottom Right |
| **Recording Timer** | Video recording time counter | Top Right |
| **Warnings & Alerts** | Critical system warnings | Center |
| **Status Icons** | Sonar, obstacle avoidance indicators | Top Center |
| **Armed/Disarmed Flash** | Motor on/off state notification | Center |
| **Remaining Flight Time** | Estimated battery to RTH time | Top Right |

## Telemetry CSV Format

Your CSV file must include the following columns:

**Required**:
- `timestamp` - ISO 8601 format (e.g., "2024-01-15 14:30:45.123")
- `camera.state.record_state` - 0=not recording, 1=starting, 2=recording, 3=stopping

**Flight Data**:
- `flight.osd.rel_h_m` - Relative altitude (meters)
- `flight.osd.vgx_mps` - Horizontal velocity X (m/s)
- `flight.osd.vgy_mps` - Horizontal velocity Y (m/s)
- `flight.osd.vgz_mps` - Vertical velocity (m/s)
- `flight.osd.pitch_deg` - Pitch angle (degrees)
- `flight.osd.roll_deg` - Roll angle (degrees)
- `flight.osd.yaw_deg` - Yaw angle (degrees)

**GPS Data**:
- `flight.osd.lat_deg` - Current latitude (decimal degrees)
- `flight.osd.lon_deg` - Current longitude (decimal degrees)
- `flight.home.lat_deg` - Home latitude (decimal degrees)
- `flight.home.lon_deg` - Home longitude (decimal degrees)
- `flight.osd.gps_nums` - GPS satellite count

**Battery Data**:
- `battery.dynamic.remain_cap_mah` - Remaining capacity (mAh)
- `battery.dynamic.full_cap_mah` - Full capacity (mAh)
- `battery.cells.cell_mv_list` - Cell voltages (pipe-separated mV)
- `flight.osd.batt_remain` - Battery percentage (0-100)

**Status Data**:
- `flight.osd.in_air` - Drone airborne status
- `flight.osd.motor_on` - Motor running status
- `flight.osd.rc_mode_channel` - Flight mode (0=N, 1=S, 2=M)
- `flight.osd.compass_over_range` - Compass error flag
- `flight.osd.is_vibrating` - Vibration warning flag
- Various other telemetry fields...

See the [CSV Schema Guide](docs/csv-schema.md) for complete reference.

## API Reference

### GUI Application

```bash
# Launch the GUI application
python dji_osd_tool.py
```

### Command-Line Interface

Generate overlays or check sync from the command line:

```bash
# Check sync between telemetry and video
python dji_osd_tool.py check <video> <csv> --flight 1

# Generate overlay (uses saved OSD settings)
python dji_osd_tool.py overlay <video> <csv> <output> --flight 1
```

### Python Library Import

```python
from dji_osd_tool_fixed import DJIOSDOverlay, OSDSettings, detect_flights
import pandas as pd

# Load telemetry
df = pd.read_csv("telemetry.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Detect flights
flights = detect_flights(df)

# Load OSD settings
settings = OSDSettings()

# Create overlay
overlay = DJIOSDOverlay(
    "input_video.mp4",
    flights[0]["df"],
    "output_video.mp4",
    osd_settings=settings,
    overlay_delay=0.5
)

# Process video
overlay.run()
```

## Configuration

### Settings File Location

- **Linux**: `~/.dji_osd_tool/osd_settings.json`
- **Windows**: `%LOCALAPPDATA%\dji_osd_tool\osd_settings.json` or `~\.dji_osd_tool\osd_settings.json`

### Settings File Format

```json
{
  "flight_mode": {
    "enabled": true,
    "dx": 0,
    "dy": 0,
    "dw": 0.0,
    "dh": 0.0
  },
  "vspeed_altitude": {
    "enabled": true,
    "dx": 0,
    "dy": 10,
    "dw": 0.0,
    "dh": 0.0
  },
  "__overlay_delay__": 0.5,
  "__global_scale__": 1.0,
  "__speed_unit__": "m/s"
}
```

**Parameters**:
- `enabled` - Show/hide element
- `dx`, `dy` - X/Y pixel offset (in 640×360 space)
- `dw`, `dh` - Width/height scale adjustment (-1.0 to 1.0)
- `__overlay_delay__` - Global overlay delay (seconds)
- `__global_scale__` - Global scaling factor
- `__speed_unit__` - Speed units (m/s, km/h, mph)

## Troubleshooting

### No flights detected
- Ensure CSV has `camera.state.record_state` column
- Check that values include 2 (recording state)
- Verify timestamp format is ISO 8601

### Large sync mismatch (> 5s)
- Confirm you selected the correct video clip
- Check if video frame rate matches telemetry sample rate
- Try adjusting overlay delay

### GPU memory error
- Enable CPU-only processing (limit resolution)
- Use Quality Reducer to downscale video first
- Increase available VRAM

### Settings not saving
- Check directory permissions: `~/.dji_osd_tool/`
- Ensure write access to home directory
- On Windows, check AppData folder permissions

### ffmpeg not found
- Install ffmpeg (see Installation section)
- The tool will automatically use OpenCV fallback
- Quality reduction limited to basic frame resizing

### Performance issues on macOS
- macOS support is limited due to GPU constraints
- Consider processing on Linux or Windows
- Use lower resolution video (720p or 480p)

## Performance Tips

1. **Faster Processing**:
   - Use lower video resolution (720p instead of 4K)
   - Reduce OSD complexity (disable unnecessary elements)
   - Process on SSD (not network drive)

2. **Better Video Quality**:
   - Use H.264 codec instead of H.265
   - Set CRF to 22 or lower (in Quality Reducer)
   - Choose 1080p or higher resolution

3. **Accurate Timing**:
   - Use high-precision timestamp format
   - Sync video/telemetry before overlay
   - Test with a short video segment first

## Architecture

### Key Components

1. **OSDSettings** - Persistent settings manager
2. **DJIOSDOverlay** - Core video processing engine
3. **OSDEditorWindow** - Visual layout editor
4. **FlightCard** - Flight selection UI
5. **App** - Main application controller

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/Devsur11/dji-osd-tool.git
cd dji-osd-tool

# Install dependencies
pip install -e ".[dev]"
```

### Building Releases

```bash
# Create a version tag
git tag -a v2.2.0 -m "Release version 2.2.0"
git push origin v2.2.0

# GitHub Actions will automatically:
# 1. Build executables for Linux and Windows
# 2. Create release with artifacts
```

### Code Style

- **Formatting**: Black (line length: 100)
- **Imports**: isort (organized by type)
- **Linting**: flake8 (with custom exclude rules)
- **Type Hints**: mypy (ignore missing imports)

## GitHub Actions Workflows

### CI/CD Pipeline

| Workflow | Trigger | Actions |
|----------|---------|---------|
| **CI** | Push/PR to main/develop | Lint, test on Python 3.8-3.12 on Linux/Windows |
| **Release** | Tag push (v*) | Build artifacts, publish to PyPI |
| **Quality** | Push/PR to main/develop | Code analysis, coverage report |
| **Issues** | Issue open/comment | Auto-label, request missing info |

All workflows run automatically on GitHub. No manual intervention needed.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Issues and discussions are encouraged. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

Built with:
- **OpenCV** - Video processing
- **pandas** - Data handling
- **NumPy** - Numerical computations
- **tkinter** - GUI framework
- **FFmpeg** - Video encoding (optional)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## Support

- **Documentation**: See [docs/](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/Devsur11/dji-osd-tool/issues)
## Disclaimer

This tool is designed for DJI Avata drone telemetry. Use responsibly and ensure compliance with local laws and regulations regarding drone footage and open-source software usage.