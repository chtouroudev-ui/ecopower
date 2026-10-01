# Nelyio - Signalisation Qualité Live (Quality Signaling Live)

Nelyio is a comprehensive quality management and live supervision system for call center operations.

## Quick Start

### Prerequisites
- Python 3.10 or later
- PostgreSQL 12+ (configured via `CONFIGURER_POSTGRESQL_AUTO.ps1`)
- Windows PowerShell 5.1+
- Caddy web server (for HTTPS)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/chtouroudev-ui/ecopower.git
   cd ecopower
   ```

2. **Configure PostgreSQL (one time only):**
   ```powershell
   .\CONFIGURER_POSTGRESQL_AUTO.ps1
   ```
   This creates the `data\postgres.env` file with your database connection string.

3. **Start the application:**
   ```powershell
   .\START_NELYIO_HTTPS.ps1
   ```
   Or for backend only:
   ```powershell
   .\START_NELYIO.ps1
   ```

### File Structure

```
ecopower/
├── *.py                      # Python application source (all at root)
├── *.ps1                     # PowerShell startup and management scripts
├── VERSION.json              # Release information and changelog
├── Caddyfile                 # HTTPS reverse proxy configuration
│
├── data/                     # Configuration and data files
│   ├── postgres.env          # PostgreSQL connection (auto-created)
│   ├── quality_*.json        # Quality system configuration
│   └── quality_scope.revision # Scope tracking file
│
├── static/                   # Frontend assets
│   ├── *.js                  # JavaScript modules
│   └── *.css                 # Stylesheets
│
├── docs/                     # Documentation
│   └── validation_final/     # Validation reports
│
└── logs/                     # Runtime logs (created on first run)
    ├── backend_9051_*.log    # Backend logs
    ├── https_launcher.log    # Launcher logs
    └── postgres_*.log        # PostgreSQL validation logs
```

## Configuration

### PostgreSQL Setup
When you run `CONFIGURER_POSTGRESQL_AUTO.ps1`, it:
1. Prompts for PostgreSQL connection details
2. Creates `data/postgres.env` with credentials
3. Validates the connection
4. Initializes the database schema

### Environment Variables
Key variables (set automatically or via `data/postgres.env`):
- `NELYIO_DATABASE_ENGINE`: Should be `postgresql`
- `NELYIO_DATABASE_URL`: PostgreSQL connection string
- `TECHIN_HOST`: Backend listening address (default: 127.0.0.1)
- `TECHIN_PORT`: Backend port (default: 9051)

## Running the Application

### HTTP Backend Only
```powershell
.\START_NELYIO.ps1
```
- Backend runs on `http://127.0.0.1:9051`
- No HTTPS; suitable for local development

### HTTPS with Caddy Reverse Proxy
```powershell
.\START_NELYIO_HTTPS.ps1
```
- Caddy runs on `https://localhost:9050` (local HTTPS)
- Backend on `http://127.0.0.1:9051` (internal only)
- Attempts to use named certificate at `stock-manager.nelyio.local:9050`

### Control Panel GUI
```powershell
.\START_NELYIO_HTTPS.ps1 -ControlPanel
```
Opens the control panel for monitoring and management.

## Troubleshooting

### "PostgreSQL n est pas encore configure"
Run the one-time setup:
```powershell
.\CONFIGURER_POSTGRESQL_AUTO.ps1
```

### Port Already in Use
Check which process holds port 9051:
```powershell
netstat -ano | findstr :9051
```
Then stop or move the old instance.

### Diagnostic Tools
Run the comprehensive diagnostic:
```powershell
.\DIAGNOSTIC_9050_9051_V50.ps1
```

Check PostgreSQL specifically:
```powershell
.\VERIFIER_POSTGRESQL.bat
```

### Logs Location
Check `logs/` directory for detailed error information:
- `backend_9051_stdout.log` - Application output
- `backend_9051_stderr.log` - Application errors
- `postgres_runtime_preflight_console.log` - Database validation
- `https_launcher.log` - Launcher diagnostics

## Architecture

### Components
1. **Backend (Python)** - HTTP API on port 9051
2. **Live Service** - Real-time monitoring and quality signaling
3. **Analytics Service** - Data analysis and reporting
4. **Caddy (Optional)** - HTTPS reverse proxy on port 9050
5. **PostgreSQL** - Primary data store

### Portability
This project is **fully portable** across different file system locations:
- All Python modules use relative paths: `Path(__file__).resolve().parent`
- All PowerShell scripts use relative paths: `$Root = Split-Path -Parent $MyInvocation.MyCommand.Path`
- Configuration is stored in the portable `data/` folder

You can:
- Clone to any local directory
- Run from a network share (e.g., `\\SERVER\Nelyio stock manager\Prod`)
- Move the entire folder to a different location without any changes

## Database

### SQLite vs PostgreSQL
- **SQLite**: Default fallback, suitable for small deployments
- **PostgreSQL**: Production mode, required for high-volume operations

### Databases
- `admin` schema: Users, settings, classifications
- `supervision` schema: Call records, quality metrics, activities
- `details` schema: Detailed event logs
- `live` schema: Current session data (SQLite only)

## Support

For issues or questions:
1. Check `logs/` directory for error details
2. Run diagnostic scripts (*.bat files)
3. Review validation reports in `docs/validation_final/`

## Version
See `VERSION.json` for current version, build information, and changelog.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
