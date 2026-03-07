# Security Policy

## Reporting Security Vulnerabilities

Please do NOT create public GitHub issues for security vulnerabilities. Instead, please report security issues privately.

### Reporting Process

1. Email security concerns to the project maintainers
2. Include detailed information about the vulnerability
3. Allow time for review and patching before public disclosure

### Security Considerations

- Always use a virtual environment when running untrusted code
- Verify dependencies are from trusted sources
- Keep Python and libraries updated
- Review the CHANGELOG for security-related fixes

## Known Issues

None currently known. If you believe you've found a security vulnerability, please report it responsibly.

## Security Best Practices for Users

When using DJI OSD Tool:

1. **File Permissions**: Ensure telemetry CSV files have appropriate read permissions only
2. **Settings Storage**: Be aware that settings are stored in plaintext JSON files
3. **Video Files**: Only process video from trusted sources
4. **Updates**: Keep the tool and dependencies updated
5. **Python Environment**: Use virtual environments to isolate dependencies

## Dependency Security

This project uses:
- opencv-python: Core computer vision library
- pandas: Data processing library
- numpy: Numerical computing library

All dependencies are from official PyPI sources. We recommend using tools like:
- `pip-audit` to check for known vulnerabilities
- `safety` to scan Python packages
- `bandit` for static security analysis

To check your environment:
```bash
pip-audit
safety check
bandit dji_osd_tool.py
```

## License

This software is provided as-is. Users assume all responsibility for security implications of their use.
