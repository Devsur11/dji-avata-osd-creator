# DJI OSD Tool - Professional On-Screen Display Overlay

A sophisticated Python tool for overlaying DJI drone telemetry data onto flight footage. Create professional-grade On-Screen Display (OSD) visualizations with a visual layout editor or command-line interface.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## Features

### Core Functionality
- **Multi-Flight Detection**: Automatically detect and process multiple flight segments from a single telemetry CSV
- **Visual OSD Editor**: Intuitive drag-and-drop layout editor for positioning OSD elements
- **Comprehensive Telemetry**: Display flight mode, altitude, speed, battery, GPS, compass, pitch/roll, warnings, and more
- **Cross-Platform**: Full support for Windows, macOS, and Linux
- **Settings Persistence**: Auto-save layout preferences to platform-specific configuration directories
- **Overlay Synchronization**: Adjust telemetry delay to correct video/telemetry misalignment

### GUI Features
- Real-time visual preview of OSD layout
- Per-element enable/disable toggles
- X/Y offset adjustment for each element
- Global scale control (0.1x to 5.0x)
- Speed unit selection (m/s, km/h, mph)
- Progress tracking and cancellation
- Video compression with resolution presets
- Professional logging interface

### OSD Elements
- **Bottom Left**: Flight mode box, vertical speed, altitude, horizontal speed, distance
- **Left Side**: Speed tape, pitch/roll indicators
- **Center**: Artificial horizon, crosshair, compassheading, warnings, armed/disarmed status
- **Right Side**: Altitude tape, temperature
- **Top Right**: Recording timer, remaining flight time, signal bars, battery, GPS satellites
- **Bottom Right**: GPS coordinates, RC/HD signal strength, battery percentage

## System Requirements

### Minimum
- Python 3.8 or higher
- 2 GB RAM
- 500 MB disk space
- Tkinter (included with most Python distributions)

### Dependencies
- opencv-python >= 4.8.0
- pandas >= 2.0.0
- numpy >= 1.24.0

### Optional
- FFmpeg (for faster video compression)

## Installation

### Quick Start (GUI)

1. **Install Python 3.8+** from [python.org](https://www.python.org)

2. **Clone or download** this repository:
   ```bash
   git clone https://github.com/Devsur11/dji-osd-tool.git
   cd dji-osd-tool
   ```

3. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**:
   ```bash
   python dji_osd_tool.py
   ```

### CLI Installation

For command-line usage only:
```bash
pip install -r requirements.txt
python dji_osd_tool.py overlay <video> <csv> <output> [--flight N]
```

### FFmpeg (Optional)

For faster video compression:

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg
```

**macOS**:
```bash
brew install ffmpeg
```

**Windows**:
Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use:
```bash
choco install ffmpeg  # If using Chocolatey
```

## Usage Guide

### GUI Mode

1. **Load Video**: Click "Browse" to select your flight video (MP4, MOV, AVI, MKV)

2. **Load Telemetry**: Select the corresponding CSV file from your drone telemetry logs

3. **Select Flight**: Choose which flight segment to process (auto-detected)

4. **Configure OSD**: 
   - Toggle elements on/off in the "OSD Layout Editor"
   - Drag elements or adjust X/Y offsets
   - Change global scale with the slider
   - Set speed units (m/s, km/h, mph)

5. **Set Output**: Choose where to save the overlay video

6. **Adjust Sync** (if needed):
   - Use "Overlay Delay" to trim off first N seconds of telemetry
   - Positive values skip telemetry; negative values skip video

7. **Generate**: Click "Generate Overlay" and monitor progress

8. **Compress** (optional):
   - Use the "Compression" tab to reduce file size
   - Select resolution and quality presets
   - FFmpeg provides faster compression if installed

### CLI Mode

#### Check telemetry/video sync:
```bash
python dji_osd_tool.py check <video.mp4> <telemetry.csv> --flight 1
```

Output shows duration differences to identify sync issues.

#### Generate overlay:
```bash
python dji_osd_tool.py overlay <video.mp4> <telemetry.csv> <output.mp4> --flight 1
```

Options:
- `--flight N`: Select flight segment (1-indexed, default: 1)

## Configuration

### Settings Storage

Settings are automatically saved to platform-specific locations:

**Windows**:
```
%LOCALAPPDATA%/dji_osd_tool/osd_settings.json
```

**macOS/Linux**:
```
~/.dji_osd_tool/osd_settings.json
```

### Settings File Format

```json
{
  "__overlay_delay__": 0.0,
  "__global_scale__": 1.0,
  "__speed_unit__": "m/s",
  "flight_mode": {
    "enabled": true,
    "dx": 0,
    "dy": 0,
    "dw": 0.0,
    "dh": 0.0
  },
  "battery": {
    "enabled": true,
    "dx": 0,
    "dy": -5,
    "dw": 0.0,
    "dh": 0.0
  }
}
```

### Manual Configuration

Edit the settings JSON file directly:
- `enabled`: Show/hide element (true/false)
- `dx`: Horizontal pixel offset
- `dy`: Vertical pixel offset
- `dw`: Width scale multiplier (-1.0 to 1.0)
- `dh`: Height scale multiplier (-1.0 to 1.0)

## Telemetry CSV Format

Your CSV file must include these timestamp and telemetry columns:

### Required Columns
- `timestamp`: ISO 8601 datetime (e.g., "2026-03-07T10:30:45.123Z")

### Location Data
- `flight.osd.lat_deg`, `flight.osd.lon_deg`: Current GPS coordinates
- `flight.home.lat_deg`, `flight.home.lon_deg`: Home location

### Flight Dynamics
- `flight.osd.vgx_mps`, `flight.osd.vgy_mps`: Horizontal velocity (m/s)
- `flight.osd.vgz_mps`: Vertical velocity (m/s)
- `flight.osd.rel_h_m`: Relative altitude (meters)
- `flight.osd.pitch_deg`, `flight.osd.roll_deg`: Attitude angles
- `flight.osd.yaw_deg`: Heading (degrees)

### Flight State
- `flight.osd.rc_mode_channel`: Flight mode (0=N, 1=S, 2=M)
- `flight.osd.motor_on`: Motor status (0/1)
- `flight.osd.in_air`: Airborne status (0/1)
- `camera.state.record_state`: Recording state (2=recording)

### Battery
- `battery.dynamic.remain_cap_mah`: Remaining capacity
- `battery.dynamic.full_cap_mah`: Full capacity
- `battery.cells.cell_mv_list`: Cell voltages (pipe-separated mV values)
- `flight.osd.batt_remain`: Legacy battery field

### Telemetry (Sensors)
- `flight.osd.gps_nums`: GPS satellite count
- `link.signal_quality`: RC signal strength (0-100)
- `link.env_quality`: HD signal strength (0-100)
- `flight.osd.is_vibrating`: Vibration detected
- `flight.osd.compass_over_range`: Compass error
- `flight.osd.accel_over_range`: Accelerometer error
- `flight.osd.esc_stall`: Motor stall detected
- `flight.osd.usonic_on`: Ultrasonic sonar active
- `flight.avoid.avoid_obstacle_working`: Obstacle avoidance active
- `flight.osd.battery_req_gohome`: Low battery return-to-home
- `flight.osd.battery_req_land`: Critical battery auto-land

## Troubleshooting

### Video File Won't Load
- Ensure video is in a supported format (MP4, MOV, AVI, MKV)
- Check file isn't corrupted: Try opening in media player
- Verify OpenCV can read it on your platform
- Try converting with FFmpeg: `ffmpeg -i input.mp4 -c:v libx264 output.mp4`

### Telemetry Issues
- Confirm CSV uses correct column names (case-sensitive)
- Verify timestamp format is ISO 8601
- Check for blank or malformed rows
- Open CSV in spreadsheet editor to inspect

### Sync Problems
- Use "Check sync" CLI command to identify drift
- Adjust "Overlay Delay" in GUI settings
- If video frame rate doesn't match telemetry sample rate, manually align

### Settings Not Saving
- Verify you have write permissions to settings directory
- Check disk space availability
- Windows users: Ensure AppData folder isn't read-only
- Linux users: Check ~/.dji_osd_tool ownership

### Performance Issues
- Reduce video resolution for faster processing
- Use compression after overlay generation
- Close other applications during processing
- Enable FFmpeg for faster compression

### Platform-Specific Issues

**Windows**:
- Update graphics drivers
- Ensure Visual C++ redistributables installed
- Use Command Prompt (not PowerShell) if issues occur

**macOS**:
- Grant microphone/camera permissions if prompted
- Update Python to latest 3.x version
- Use homebrew to install dependencies

**Linux**:
- Install libgl1-mesa-glx for OpenCV: `sudo apt-get install libgl1-mesa-glx`
- Use apt/yum to install system dependencies
- Try running with DISPLAY variable if headless

## Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/Devsur11/dji-osd-tool.git
cd dji-osd-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies and dev tools
pip install -r requirements.txt
pip install flake8 pylint bandit
```

### Code Quality

```bash
# Lint
flake8 dji_osd_tool.py --max-line-length=120

# Security analysis
bandit dji_osd_tool.py

# Import test
python -c "import dji_osd_tool; print('OK')"
```

### Project Structure

```
dji-osd-tool/
├── dji_osd_tool.py          # Main application (2000+ lines)
├── requirements.txt         # Python dependencies
├── setup.py                # Package configuration
├── README.md               # This file
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # MIT License
├── .gitignore             # Git ignore patterns
├── .flake8                # Flake8 linting config
└── .github/
    └── workflows/
        ├── quality.yml     # Code quality CI
        ├── release.yml     # Release automation
        └── issue-summary.yml # Issue processing
```

### Key Classes and Functions

**OSDSettings**
- Persistent configuration management
- Per-element positioning and scaling
- Speed unit conversion

**DJIOSDOverlay**
- Frame-by-frame telemetry overlay
- OSD element rendering
- Video encoding to MP4

**Utility Functions**
- `detect_flights()`: Multi-flight segmentation
- `get_video_info()`: Video metadata extraction
- `_calc_batt_pct()`: Battery percentage calculations

**GUI Components**
- Flight selection interface
- OSD editor with drag-and-drop
- Progress tracking and logging
- Compression utilities

## Performance Guidelines

- Video resolution: 1920x1080 baseline for OSD sizing
- Processing speed: ~20-30 FPS depending on system
- Memory usage: ~200-500 MB during processing
- File output: Similar size to input (overlay adds ~5-10%)

## License

MIT License - See [LICENSE](LICENSE) file for details

Free to use, modify, and distribute with attribution.


## Support

- GitHub Issues: [Report bugs or request features](https://github.com/Devsur11/dji-osd-tool/issues)
- Documentation: Check README and inline code comments

## Disclaimer

This tool is provided as-is for personal, educational, and professional use. Users are responsible for:
- Ensuring compliance with local regulations regarding drone operations
- Respecting copyright and intellectual property rights
- Using generated videos ethically and legally

The authors are not liable for misuse or damages resulting from this software.

---

**Last Updated**: March 2026 | Version 2.2.0
