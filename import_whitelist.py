#!/usr/bin/env python3
"""
Import members from CSV into Supabase whitelist table
Batch imports for performance, skips duplicates
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

console = Console()

class WhitelistImporter:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            console.print("[red]❌ Missing Supabase credentials in .env file[/red]")
            sys.exit(1)
        
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.batch_size = 100
        self.stats = {
            'total_in_csv': 0,
            'imported': 0,
            'skipped_duplicates': 0,
            'errors': 0,
            'error_details': []
        }
    
    def read_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """Read members from CSV file"""
        members = []
        
        if not Path(filepath).exists():
            console.print(f"[red]❌ File not found: {filepath}[/red]")
            sys.exit(1)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                members.append({
                    'user_id': int(row['user_id']),
                    'username': row.get('username', ''),
                    'first_name': row.get('first_name', ''),
                    'last_name': row.get('last_name', ''),
                    'is_premium': row.get('is_premium', '').lower() == 'true',
                    'joined_date': row.get('joined_date', ''),
                })
        
        self.stats['total_in_csv'] = len(members)
        return members
    
    def check_existing(self, user_ids: List[int]) -> set:
        """Check which user IDs already exist in whitelist"""
        try:
            # Query existing telegram_ids
            result = self.supabase.table('whitelist').select('telegram_id').in_('telegram_id', user_ids).execute()
            existing_ids = {row['telegram_id'] for row in result.data}
            return existing_ids
        except Exception as e:
            console.print(f"[yellow]⚠️  Error checking existing: {e}[/yellow]")
            return set()
    
    def import_batch(self, batch: List[Dict[str, Any]]) -> tuple:
        """Import a batch of members"""
        user_ids = [m['user_id'] for m in batch]
        
        # Check for existing entries
        existing = self.check_existing(user_ids)
        
        # Filter out duplicates
        new_members = []
        for member in batch:
            if member['user_id'] in existing:
                self.stats['skipped_duplicates'] += 1
            else:
                new_members.append({
                    'telegram_id': member['user_id'],  # Map user_id to telegram_id
                    'source': 'initial_import',
                    'note': f"Imported from CSV - {member['first_name']} {member['last_name']} (@{member['username']})",
                    'granted_at': datetime.now().isoformat()  # Use granted_at instead of created_at
                })
        
        # Insert new members
        if new_members:
            try:
                result = self.supabase.table('whitelist').insert(new_members).execute()
                imported_count = len(result.data)
                self.stats['imported'] += imported_count
                return imported_count, 0
            except Exception as e:
                self.stats['errors'] += len(new_members)
                self.stats['error_details'].append(str(e))
                return 0, len(new_members)
        
        return 0, 0
    
    def import_members(self, filepath: str):
        """Main import function"""
        console.print("\n[bold cyan]🚀 Whitelist Import Tool[/bold cyan]")
        console.print("="*50)
        
        # Read CSV
        console.print(f"\n📂 Reading: {filepath}")
        members = self.read_csv(filepath)
        console.print(f"✅ Found {len(members)} members in CSV")
        
        # Check table exists
        console.print("\n🔍 Checking whitelist table...")
        try:
            result = self.supabase.table('whitelist').select('count', count='exact').limit(1).execute()
            existing_count = result.count
            console.print(f"✅ Table exists with {existing_count} existing entries")
        except Exception as e:
            console.print(f"[red]❌ Error accessing whitelist table: {e}[/red]")
            sys.exit(1)
        
        # Import in batches
        console.print(f"\n📥 Importing in batches of {self.batch_size}...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Importing members...", total=len(members))
            
            for i in range(0, len(members), self.batch_size):
                batch = members[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(members) + self.batch_size - 1) // self.batch_size
                
                progress.update(task, description=f"Batch {batch_num}/{total_batches}")
                
                imported, errors = self.import_batch(batch)
                
                progress.advance(task, len(batch))
        
        # Display results
        self.display_results()
    
    def display_results(self):
        """Display import statistics"""
        console.print("\n" + "="*50)
        console.print("[bold green]✅ Import Complete![/bold green]\n")
        
        # Create results table
        table = Table(title="Import Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        
        table.add_row("Total in CSV", str(self.stats['total_in_csv']))
        table.add_row("Successfully imported", str(self.stats['imported']))
        table.add_row("Skipped (duplicates)", str(self.stats['skipped_duplicates']))
        table.add_row("Errors", str(self.stats['errors']))
        
        console.print(table)
        
        # Show errors if any
        if self.stats['error_details']:
            console.print("\n[yellow]⚠️  Errors encountered:[/yellow]")
            for error in self.stats['error_details'][:5]:  # Show first 5 errors
                console.print(f"   - {error}")
        
        # Final summary
        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"   • {self.stats['imported']} new members added to whitelist")
        console.print(f"   • {self.stats['skipped_duplicates']} duplicates skipped")
        
        if self.stats['imported'] > 0:
            console.print(f"\n[green]🎉 Whitelist updated successfully![/green]")
            console.print(f"   All {self.stats['imported']} members now have free access.")
            console.print(f"   New members joining after deployment will need to pay.")

def main():
    # Check for CSV file
    csv_file = "members_20250906_030623.csv"
    
    if not Path(csv_file).exists():
        # Try to find the most recent members file
        csv_files = list(Path('.').glob('members_*.csv'))
        if csv_files:
            csv_file = str(max(csv_files, key=lambda x: x.stat().st_mtime))
            console.print(f"[yellow]Using most recent file: {csv_file}[/yellow]")
        else:
            console.print("[red]❌ No members CSV file found[/red]")
            sys.exit(1)
    
    # Confirm before importing
    console.print(f"\n[bold]Ready to import from: {csv_file}[/bold]")
    console.print("This will add all members to the whitelist table.")
    
    response = input("\nProceed with import? (y/n): ").strip().lower()
    if response != 'y':
        console.print("[yellow]Import cancelled[/yellow]")
        sys.exit(0)
    
    # Run import
    importer = WhitelistImporter()
    importer.import_members(csv_file)

if __name__ == "__main__":
    main()