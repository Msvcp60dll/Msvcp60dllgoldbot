"""Simple database migration runner for PostgreSQL"""

import asyncio
import asyncpg
import os
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Runs SQL migrations in order, tracking applied migrations in database"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent
        
    async def initialize(self):
        """Create migrations tracking table if not exists"""
        async with asyncpg.connect(self.database_url) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    execution_time_ms INTEGER,
                    checksum VARCHAR(64)
                );
                
                CREATE INDEX IF NOT EXISTS idx_migrations_applied_at 
                    ON schema_migrations(applied_at DESC);
            """)
            logger.info("Migrations table ready")
    
    async def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migration versions"""
        async with asyncpg.connect(self.database_url) as conn:
            rows = await conn.fetch("""
                SELECT version FROM schema_migrations 
                ORDER BY version
            """)
            return [row['version'] for row in rows]
    
    def get_migration_files(self) -> List[Tuple[str, Path]]:
        """Get all migration SQL files in order"""
        migrations = []
        
        # Look for files matching pattern: 001_name.sql, 002_name.sql, etc.
        for file_path in sorted(self.migrations_dir.glob("*.sql")):
            match = re.match(r'^(\d{3})_.*\.sql$', file_path.name)
            if match:
                version = match.group(1)
                migrations.append((version, file_path))
        
        return migrations
    
    def parse_migration_file(self, file_path: Path) -> Tuple[str, str]:
        """Parse migration file to extract UP and DOWN sections"""
        content = file_path.read_text()
        
        # Split by -- UP and -- DOWN markers
        up_match = re.search(r'-- UP\n(.*?)(?:-- DOWN|$)', content, re.DOTALL)
        down_match = re.search(r'-- DOWN\n(.*?)$', content, re.DOTALL)
        
        up_sql = up_match.group(1).strip() if up_match else content.strip()
        down_sql = down_match.group(1).strip() if down_match else ""
        
        return up_sql, down_sql
    
    def calculate_checksum(self, content: str) -> str:
        """Calculate checksum of migration content"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def apply_migration(self, version: str, file_path: Path) -> bool:
        """Apply a single migration"""
        try:
            up_sql, _ = self.parse_migration_file(file_path)
            checksum = self.calculate_checksum(up_sql)
            
            async with asyncpg.connect(self.database_url) as conn:
                # Start transaction
                async with conn.transaction():
                    start_time = datetime.now(timezone.utc)
                    
                    # Execute migration SQL
                    logger.info(f"Applying migration {version}: {file_path.name}")
                    
                    # Split by semicolon but keep statements that might contain semicolons in strings
                    statements = self._split_sql_statements(up_sql)
                    
                    for statement in statements:
                        if statement.strip():
                            await conn.execute(statement)
                    
                    # Record migration
                    execution_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    
                    await conn.execute("""
                        INSERT INTO schema_migrations (version, applied_at, execution_time_ms, checksum)
                        VALUES ($1, $2, $3, $4)
                    """, version, datetime.now(timezone.utc), execution_time_ms, checksum)
                    
                    logger.info(f"✅ Applied migration {version} ({execution_time_ms}ms)")
                    return True
                    
        except asyncpg.UniqueViolationError:
            logger.info(f"Migration {version} already applied")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to apply migration {version}: {e}")
            raise
    
    async def rollback_migration(self, version: str, file_path: Path) -> bool:
        """Rollback a single migration"""
        try:
            _, down_sql = self.parse_migration_file(file_path)
            
            if not down_sql:
                logger.warning(f"No DOWN section in migration {version}")
                return False
            
            async with asyncpg.connect(self.database_url) as conn:
                async with conn.transaction():
                    logger.info(f"Rolling back migration {version}: {file_path.name}")
                    
                    # Execute rollback SQL
                    statements = self._split_sql_statements(down_sql)
                    for statement in statements:
                        if statement.strip():
                            await conn.execute(statement)
                    
                    # Remove migration record
                    await conn.execute("""
                        DELETE FROM schema_migrations WHERE version = $1
                    """, version)
                    
                    logger.info(f"✅ Rolled back migration {version}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Failed to rollback migration {version}: {e}")
            raise
    
    def _split_sql_statements(self, sql: str) -> List[str]:
        """Split SQL into individual statements, handling strings properly"""
        statements = []
        current = []
        in_string = False
        string_char = None
        
        for i, char in enumerate(sql):
            if not in_string:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                elif char == ';':
                    # End of statement
                    current.append(char)
                    statements.append(''.join(current))
                    current = []
                    continue
            else:
                if char == string_char:
                    # Check if it's escaped
                    if i > 0 and sql[i-1] != '\\':
                        in_string = False
                        string_char = None
            
            current.append(char)
        
        # Add remaining statement if exists
        if current:
            remaining = ''.join(current).strip()
            if remaining:
                statements.append(remaining)
        
        return statements
    
    async def run_pending_migrations(self) -> int:
        """Run all pending migrations"""
        await self.initialize()
        
        applied = await self.get_applied_migrations()
        all_migrations = self.get_migration_files()
        
        pending = [(v, p) for v, p in all_migrations if v not in applied]
        
        if not pending:
            logger.info("No pending migrations")
            return 0
        
        logger.info(f"Found {len(pending)} pending migration(s)")
        
        for version, file_path in pending:
            await self.apply_migration(version, file_path)
        
        return len(pending)
    
    async def status(self) -> dict:
        """Get migration status"""
        await self.initialize()
        
        applied = await self.get_applied_migrations()
        all_migrations = self.get_migration_files()
        
        pending = [(v, p.name) for v, p in all_migrations if v not in applied]
        
        async with asyncpg.connect(self.database_url) as conn:
            latest = await conn.fetchrow("""
                SELECT version, applied_at, execution_time_ms 
                FROM schema_migrations 
                ORDER BY applied_at DESC 
                LIMIT 1
            """)
        
        return {
            "total_migrations": len(all_migrations),
            "applied_migrations": len(applied),
            "pending_migrations": len(pending),
            "pending_list": pending,
            "latest_applied": {
                "version": latest['version'],
                "applied_at": latest['applied_at'].isoformat(),
                "execution_time_ms": latest['execution_time_ms']
            } if latest else None
        }
    
    async def rollback_last(self) -> bool:
        """Rollback the last applied migration"""
        await self.initialize()
        
        async with asyncpg.connect(self.database_url) as conn:
            latest = await conn.fetchrow("""
                SELECT version FROM schema_migrations 
                ORDER BY version DESC 
                LIMIT 1
            """)
        
        if not latest:
            logger.info("No migrations to rollback")
            return False
        
        version = latest['version']
        migrations = dict(self.get_migration_files())
        
        if version not in migrations:
            logger.error(f"Migration file not found for version {version}")
            return False
        
        return await self.rollback_migration(version, migrations[version])