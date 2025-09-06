#!/usr/bin/env python3
"""
Verify whitelist import - check counts and show samples
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

console = Console()

def verify_import():
    """Verify the whitelist import worked correctly"""
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        console.print("[red]❌ Missing Supabase credentials in .env file[/red]")
        sys.exit(1)
    
    console.print("\n[bold cyan]🔍 Whitelist Verification Tool[/bold cyan]")
    console.print("="*50)
    
    try:
        # Connect to Supabase
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        # Get total count
        console.print("\n📊 Checking whitelist table...")
        result = supabase.table('whitelist').select('*', count='exact').execute()
        total_count = result.count
        
        console.print(f"✅ Total entries in whitelist: [bold green]{total_count}[/bold green]")
        
        # Count by source
        console.print("\n📈 Breakdown by source:")
        
        # Get counts by source
        sources = {}
        for row in result.data:
            source = row.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        source_table = Table(title="Whitelist Sources")
        source_table.add_column("Source", style="cyan")
        source_table.add_column("Count", justify="right", style="green")
        source_table.add_column("Percentage", justify="right")
        
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_count * 100) if total_count > 0 else 0
            source_table.add_row(source, str(count), f"{percentage:.1f}%")
        
        console.print(source_table)
        
        # Show sample entries
        console.print("\n📋 Sample entries (most recent):")
        
        # Get most recent entries
        recent = supabase.table('whitelist')\
            .select('telegram_id, source, note, granted_at, revoked_at')\
            .order('granted_at', desc=True)\
            .limit(10)\
            .execute()
        
        if recent.data:
            sample_table = Table(title="Recent Whitelist Entries")
            sample_table.add_column("User ID", style="cyan")
            sample_table.add_column("Source", style="yellow")
            sample_table.add_column("Status", style="green")
            sample_table.add_column("Created", style="magenta")
            
            for entry in recent.data[:10]:
                user_id = str(entry['telegram_id'])
                source = entry['source']
                status = "Revoked" if entry.get('revoked_at') else "Active"
                created = entry['granted_at'][:19] if entry['granted_at'] else 'Unknown'
                
                sample_table.add_row(user_id, source, status, created)
            
            console.print(sample_table)
        
        # Check for recent imports
        console.print("\n🕐 Recent import activity:")
        
        # Count entries created in last hour
        from datetime import datetime, timedelta
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        recent_imports = supabase.table('whitelist')\
            .select('*', count='exact')\
            .gte('granted_at', one_hour_ago)\
            .execute()
        
        if recent_imports.count > 0:
            console.print(f"   • [green]{recent_imports.count} entries added in the last hour[/green]")
        else:
            console.print("   • No entries added in the last hour")
        
        # Count initial_import entries
        initial_imports = supabase.table('whitelist')\
            .select('*', count='exact')\
            .eq('source', 'initial_import')\
            .execute()
        
        console.print(f"   • [cyan]{initial_imports.count} entries from 'initial_import'[/cyan]")
        
        # Summary
        console.print("\n" + "="*50)
        if total_count > 0:
            console.print("[bold green]✅ Whitelist is populated and ready![/bold green]")
            console.print(f"\n📌 Summary:")
            console.print(f"   • Total whitelisted users: {total_count}")
            console.print(f"   • Initial import entries: {initial_imports.count}")
            console.print(f"   • These users have free access forever")
            console.print(f"   • New members will need to pay after deployment")
            
            console.print(f"\n🚀 Ready to deploy with: [bold]railway up[/bold]")
        else:
            console.print("[yellow]⚠️  Whitelist is empty - run import_whitelist.py first[/yellow]")
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    verify_import()