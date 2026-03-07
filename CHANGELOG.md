# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2024-03-07

### Added
- Cross-platform path handling for settings storage
- Support for Windows AppData directory
- Full macOS and Linux compatibility
- GitHub Actions for continuous integration
- Automated release creation from tags
- Code quality checks (flake8, pylint, bandit)
- Comprehensive documentation and CONTRIBUTING guidelines

### Changed
- Improved platform detection for settings directory
- Enhanced error handling for missing settings files

### Fixed
- Settings path compatibility across operating systems

## [2.1.0] - 2024-01-15

### Added
- Visual OSD layout editor with drag-and-drop support
- Multi-flight detection from single CSV
- Global scale and offset adjustments
- Recording timer OSD element
- Status icons and warnings display
- Video compression utility with resolution presets

### Features
- GPS satellite count with DJI-style icon
- Battery percentage calculation from multiple sources
- Speed units switching (m/s, km/h, mph)
- Overlay delay adjustment for sync correction

## [2.0.0] - 2023-12-01

### Added
- GUI Edition with Tkinter interface
- Real-time OSD preview
- Settings persistence to local JSON file
- CLI support for batch processing
- Multiple telemetry data sources support

### Changed
- Complete rewrite from original DJI OSD tool
- Improved accuracy of OSD element positioning
- Enhanced battery calculation algorithms

## [1.0.0] - 2023-11-01

### Added
- Initial release
- Basic OSD overlay functionality
- CSV telemetry support
- Video processing with OpenCV
