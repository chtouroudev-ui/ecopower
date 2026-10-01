# Data Directory

This directory contains configuration and reference data for the Nelyio system.

## Files

### postgres.env
**Created by:** `CONFIGURER_POSTGRESQL_AUTO.ps1` (first run only)  
**Purpose:** PostgreSQL connection configuration  
**Content:** Environment variables for database access
```
NELYIO_DATABASE_ENGINE=postgresql
NELYIO_DATABASE_URL=postgresql://user:password@host:5432/database
```
**Note:** This file contains credentials and should NOT be shared or committed to git.

### quality_last_import.json
**Purpose:** Last quality system configuration import metadata  
**Content:** Tracking information for the latest quality configuration  
**Auto-created:** During first quality system initialization

### quality_priorities.json
**Purpose:** Quality priority metrics and thresholds  
**Content:** Configuration for quality scoring rules and alert levels  
**Size:** Typically 1-2 MB with complete priority definitions

### quality_priorities.previous.json
**Purpose:** Backup of previous quality priority configuration  
**Content:** Previous version of quality_priorities.json  
**Auto-updated:** When quality rules are updated

### quality_scope.revision
**Purpose:** Quality scope revision tracking  
**Content:** Version identifier for scope configuration  
**Usage:** Prevents redundant recalculations of quality metrics

## Setup Instructions

1. **PostgreSQL Configuration:**
   After cloning, run once:
   ```powershell
   .\CONFIGURER_POSTGRESQL_AUTO.ps1
   ```
   This will create `postgres.env` with your database connection.

2. **Quality Configuration:**
   The quality system automatically initializes on first run:
   - Loads existing configuration if available
   - Creates default configuration if missing
   - Stores import history in `quality_last_import.json`

3. **Moving Projects:**
   All files in this directory use relative paths, so you can:
   - Copy the entire project to a different location
   - Move it to a network share
   - Clone to different machines
   
   No absolute paths need to be updated.

## Security Notes

- **postgres.env**: Contains database credentials - keep private
- Do NOT commit `postgres.env` to version control
- Each installation should have its own `postgres.env`
- Never share database credentials via git or other shared systems

## Troubleshooting

**Issue:** "postgres.env not found"  
**Solution:** Run `CONFIGURER_POSTGRESQL_AUTO.ps1`

**Issue:** Database connection fails  
**Solution:** Check `postgres.env` connection string format:
```
postgresql://username:password@localhost:5432/database_name
```

**Issue:** Quality metrics not loading  
**Solution:** Check that quality_*.json files are readable and not corrupted
