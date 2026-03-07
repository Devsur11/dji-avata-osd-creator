# Contributing to DJI OSD Tool

Thank you for your interest in contributing to the DJI OSD Tool! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Report issues professionally
- Respect intellectual property

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/dji-osd-tool.git
   cd dji-osd-tool
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   pip install flake8 pylint bandit
   ```

## Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes following these guidelines:
   - Follow PEP 8 style guide
   - Keep functions focused and well-documented
   - Add comments for complex logic
   - Test on multiple platforms if possible

3. Run quality checks:
   ```bash
   flake8 dji_osd_tool.py --max-line-length=120
   pylint dji_osd_tool.py
   bandit dji_osd_tool.py
   ```

4. Test your changes:
   ```bash
   python dji_osd_tool.py --help
   ```

## Testing Requirements

- Code must pass flake8 linting
- Should work on Python 3.8+
- Cross-platform compatibility (Windows, macOS, Linux)
- No breaking changes to the public API

## Submitting Changes

1. Commit your changes with clear messages:
   ```bash
   git commit -m "Add: clear description of changes"
   ```
2. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
3. Create a Pull Request with:
   - Clear title describing the change
   - Description of what was changed and why
   - Reference to related issues (if any)
   - Testing information

## Bug Reports

When reporting bugs, include:
- Operating system and Python version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Any error messages or logs

## Feature Requests

Describe:
- What you want to add
- Why it would be useful
- How it should work
- Any alternative approaches you've considered

## Documentation

- Update README.md for user-facing changes
- Add comments to code for complex logic
- Update CHANGELOG.md with significant changes
- Document new features or command-line options

## Release Process

Releases are created from annotated git tags following semantic versioning:
- `v2.1.0` for new features
- `v2.0.1` for bug fixes
- `v3.0.0` for breaking changes

Tags trigger automatic GitHub Actions that create releases and artifacts.

## Questions?

- Check existing issues and discussions
- Review the README.md for usage information
- Look at code comments and docstrings
- Open an issue for clarification

Thank you for contributing!
