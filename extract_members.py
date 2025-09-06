#!/usr/bin/env python3
"""
Interactive member extraction and whitelist import tool.
Extracts all group members and optionally imports directly to Supabase.

Requirements:
    pip install pyrogram tgcrypto supabase python-dotenv rich
"""

import asyncio
import csv
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import json

# Third-party imports
try:
    from pyrogram import Client
    from pyrogram.types import ChatMember
    from pyrogram.enums import ChatMemberStatus
    from pyrogram.errors import FloodWait, SessionPasswordNeeded
    from supabase import create_client, Client as SupabaseClient
    from dotenv import load_dotenv
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
except ImportError as e:
    print("Missing dependencies! Install with:")
    print("pip install pyrogram tgcrypto supabase python-dotenv rich")
    print(f"\nError: {e}")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configuration (hardcoded as requested)
API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"
GROUP_CHAT_ID = 2384609739

# Rich console for beautiful output
console = Console()


class MemberExtractor:
    def __init__(self):
        self.app = None
        self.supabase = None
        self.members = []
        self.group_info = None
        self.session_name = "member_extractor"
        
    async def setup_telegram(self):
        """Setup Pyrogram client with interactive authentication"""
        console.print("\n[bold cyan]📱 Connecting to Telegram...[/bold cyan]")
        
        # Create client
        self.app = Client(
            self.session_name,
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        # Check if session exists
        session_file = Path(f"{self.session_name}.session")
        is_new_session = not session_file.exists()
        
        if is_new_session:
            console.print("[yellow]New session detected. You'll need to authenticate.[/yellow]")
        else:
            console.print("[green]Using existing session...[/green]")
        
        try:
            # Start client
            await self.app.start()
            
            # If new session, we already went through auth in start()
            me = await self.app.get_me()
            console.print(f"[green]✅ Logged in as:[/green] {me.first_name} (@{me.username or 'no username'})")
            
            return True
            
        except Exception as e:
            if "phone number" in str(e).lower():
                # Need phone number
                phone = Prompt.ask("\n[bold]Enter phone number[/bold] (with country code, e.g., +1234567890)")
                
                try:
                    await self.app.connect()
                    sent_code = await self.app.send_code(phone)
                    
                    console.print("[green]✅ Code sent to Telegram![/green]")
                    code = Prompt.ask("[bold]Enter verification code[/bold]")
                    
                    # Try to sign in
                    try:
                        await self.app.sign_in(phone, sent_code.phone_code_hash, code)
                    except SessionPasswordNeeded:
                        # 2FA enabled
                        password = Prompt.ask("[bold]Two-factor authentication enabled. Enter password[/bold]", password=True)
                        await self.app.check_password(password)
                    
                    await self.app.disconnect()
                    await self.app.start()
                    
                    me = await self.app.get_me()
                    console.print(f"[green]✅ Logged in as:[/green] {me.first_name} (@{me.username or 'no username'})")
                    return True
                    
                except Exception as auth_error:
                    console.print(f"[red]❌ Authentication failed: {auth_error}[/red]")
                    return False
            else:
                console.print(f"[red]❌ Connection failed: {e}[/red]")
                return False
    
    def setup_supabase(self) -> bool:
        """Setup Supabase client from .env file"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            console.print("[yellow]⚠️  Supabase credentials not found in .env file[/yellow]")
            console.print("Add SUPABASE_URL and SUPABASE_SERVICE_KEY to your .env file")
            return False
        
        try:
            self.supabase = create_client(supabase_url, supabase_key)
            console.print("[green]✅ Connected to Supabase[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Supabase connection failed: {e}[/red]")
            return False
    
    async def verify_group(self) -> bool:
        """Verify we can access the target group"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Checking group access...", total=None)
            
            try:
                self.group_info = await self.app.get_chat(GROUP_CHAT_ID)
                progress.update(task, completed=100)
                
                # Create info table
                table = Table(title=f"Group: {self.group_info.title}", show_header=False)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")
                
                table.add_row("Chat ID", str(GROUP_CHAT_ID))
                table.add_row("Type", str(self.group_info.type))
                table.add_row("Members", str(self.group_info.members_count))
                
                # Check our membership
                me = await self.app.get_me()
                try:
                    my_status = await self.app.get_chat_member(GROUP_CHAT_ID, me.id)
                    table.add_row("Your Status", str(my_status.status.name))
                    
                    if my_status.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
                        console.print("[red]⚠️  You're not a member of this group![/red]")
                        return False
                except:
                    table.add_row("Your Status", "Unknown")
                
                console.print(table)
                return True
                
            except Exception as e:
                console.print(f"[red]❌ Error accessing group: {e}[/red]")
                return False
    
    async def extract_members(self, dry_run: bool = False) -> bool:
        """Extract all members from the group"""
        console.print(f"\n[bold]📥 Extracting members from group {GROUP_CHAT_ID}...[/bold]")
        
        self.members = []
        bots_skipped = 0
        deleted_skipped = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # Get total count first (approximate)
            total = self.group_info.members_count or 1000
            task = progress.add_task("Extracting members...", total=total)
            
            try:
                async for member in self.app.get_chat_members(GROUP_CHAT_ID):
                    # Skip deleted accounts
                    if member.user.is_deleted:
                        deleted_skipped += 1
                        progress.advance(task)
                        continue
                    
                    # Skip bots
                    if member.user.is_bot:
                        bots_skipped += 1
                        progress.advance(task)
                        continue
                    
                    # Collect member data
                    member_data = {
                        'user_id': member.user.id,
                        'username': member.user.username or '',
                        'first_name': (member.user.first_name or '').replace("'", "''"),  # Escape quotes
                        'last_name': (member.user.last_name or '').replace("'", "''"),
                        'status': member.status.name,
                        'is_admin': member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR],
                        'joined_date': member.joined_date.isoformat() if member.joined_date else '',
                        'is_premium': getattr(member.user, 'is_premium', False)
                    }
                    
                    self.members.append(member_data)
                    
                    # Update progress
                    progress.update(
                        task, 
                        completed=len(self.members) + bots_skipped + deleted_skipped,
                        description=f"Extracted {len(self.members)} valid members..."
                    )
                    
                    # Rate limit protection
                    if len(self.members) % 200 == 0:
                        await asyncio.sleep(0.5)
                        
            except FloodWait as e:
                console.print(f"[yellow]⚠️  Rate limited. Waiting {e.value} seconds...[/yellow]")
                await asyncio.sleep(e.value)
                return await self.extract_members(dry_run)
                
            except Exception as e:
                console.print(f"[red]❌ Extraction error: {e}[/red]")
                return False
        
        # Show summary
        console.print(f"\n[green]✅ Extraction complete![/green]")
        console.print(f"   Valid members: [bold]{len(self.members)}[/bold]")
        console.print(f"   Bots skipped: {bots_skipped}")
        console.print(f"   Deleted accounts skipped: {deleted_skipped}")
        
        # Show sample in dry run
        if dry_run and self.members:
            table = Table(title="Sample Members (first 5)")
            table.add_column("User ID", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Username", style="yellow")
            table.add_column("Status", style="green")
            
            for member in self.members[:5]:
                table.add_row(
                    str(member['user_id']),
                    f"{member['first_name']} {member['last_name']}".strip(),
                    f"@{member['username']}" if member['username'] else "-",
                    member['status']
                )
            
            console.print(table)
            if len(self.members) > 5:
                console.print(f"   ... and {len(self.members) - 5} more members")
        
        return True
    
    def save_to_csv(self) -> str:
        """Save members to CSV file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"members_backup_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['user_id', 'username', 'first_name', 'last_name', 
                         'status', 'is_admin', 'joined_date', 'is_premium']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for member in self.members:
                writer.writerow(member)
        
        console.print(f"[green]📁 Backup saved:[/green] {filename}")
        return filename
    
    async def check_existing_whitelist(self) -> Dict[int, bool]:
        """Check which members are already whitelisted"""
        if not self.supabase:
            return {}
        
        existing = {}
        user_ids = [m['user_id'] for m in self.members]
        
        # Check in batches
        batch_size = 100
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i+batch_size]
            try:
                response = self.supabase.table('whitelist').select('user_id').in_('user_id', batch).execute()
                for row in response.data:
                    existing[row['user_id']] = True
            except Exception as e:
                console.print(f"[yellow]Warning: Could not check existing whitelist: {e}[/yellow]")
                break
        
        return existing
    
    async def import_to_supabase(self) -> bool:
        """Import members directly to Supabase whitelist table"""
        if not self.supabase:
            console.print("[red]❌ Supabase not configured[/red]")
            return False
        
        # Check existing members
        console.print("\n[cyan]Checking for existing whitelist entries...[/cyan]")
        existing = await self.check_existing_whitelist()
        
        # Filter out existing
        new_members = [m for m in self.members if m['user_id'] not in existing]
        
        if existing:
            console.print(f"[yellow]Found {len(existing)} members already whitelisted[/yellow]")
        
        if not new_members:
            console.print("[green]✅ All members are already whitelisted![/green]")
            return True
        
        console.print(f"[bold]Will import {len(new_members)} new members[/bold]")
        
        if not Confirm.ask("Proceed with import?"):
            return False
        
        # Import in batches
        batch_size = 100
        imported = 0
        failed = 0
        
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            total_batches = (len(new_members) + batch_size - 1) // batch_size
            task = progress.add_task("Importing to Supabase...", total=len(new_members))
            
            for i in range(0, len(new_members), batch_size):
                batch = new_members[i:i+batch_size]
                batch_num = (i // batch_size) + 1
                
                # Prepare batch data
                batch_data = []
                for member in batch:
                    username = member['username'] or 'no_username'
                    name = f"{member['first_name']} {member['last_name']}".strip() or 'Unknown'
                    note = f"Initial import - {name} (@{username})"
                    if member['is_admin']:
                        note += " [ADMIN]"
                    
                    batch_data.append({
                        'user_id': member['user_id'],
                        'source': 'initial_import',
                        'note': note,
                        'created_at': datetime.now().isoformat()
                    })
                
                # Insert batch
                try:
                    response = self.supabase.table('whitelist').insert(batch_data).execute()
                    imported += len(batch)
                    progress.update(task, completed=imported)
                    progress.update(task, description=f"Importing batch {batch_num}/{total_batches}...")
                    
                except Exception as e:
                    console.print(f"[red]❌ Batch {batch_num} failed: {e}[/red]")
                    failed += len(batch)
                    progress.update(task, completed=imported + failed)
                
                # Small delay between batches
                await asyncio.sleep(0.2)
        
        # Summary
        console.print(f"\n[green]✅ Import complete![/green]")
        console.print(f"   Successfully imported: [bold green]{imported}[/bold green]")
        if failed > 0:
            console.print(f"   Failed: [bold red]{failed}[/bold red]")
        
        return imported > 0
    
    def generate_sql_file(self) -> str:
        """Generate SQL file for manual import"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"whitelist_import_{timestamp}.sql"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("-- Whitelist import for existing group members\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Total members: {len(self.members)}\n\n")
            
            f.write("INSERT INTO whitelist (user_id, source, note, created_at)\nVALUES\n")
            
            values = []
            for member in self.members:
                username = member['username'] or 'no_username'
                name = f"{member['first_name']} {member['last_name']}".strip() or 'Unknown'
                note = f"Initial import - {name} (@{username})"
                if member['is_admin']:
                    note += " [ADMIN]"
                note = note.replace("'", "''")  # Escape quotes
                
                values.append(f"    ({member['user_id']}, 'initial_import', '{note}', NOW())")
            
            f.write(",\n".join(values))
            f.write("\nON CONFLICT (user_id) DO NOTHING;\n")
        
        console.print(f"[green]📁 SQL file saved:[/green] {filename}")
        return filename
    
    async def cleanup(self):
        """Cleanup and disconnect"""
        if self.app:
            await self.app.stop()
    
    async def run(self):
        """Main interactive flow"""
        # Display header
        console.print(Panel.fit(
            "[bold cyan]Member Extraction Tool[/bold cyan]\n"
            f"Group: {GROUP_CHAT_ID}",
            title="🚀 Telegram Whitelist Import"
        ))
        
        # Show menu
        console.print("\n[bold]Choose an option:[/bold]")
        console.print("[1] Extract and save to file only")
        console.print("[2] Extract and import to Supabase")
        console.print("[3] Dry run (preview only)")
        
        choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="2")
        
        try:
            # Setup Telegram
            if not await self.setup_telegram():
                return False
            
            # Verify group
            if not await self.verify_group():
                return False
            
            # Handle based on choice
            if choice == "3":
                # Dry run
                await self.extract_members(dry_run=True)
                console.print("\n[yellow]This was a dry run. No files were created.[/yellow]")
                
            elif choice == "1":
                # Extract and save only
                if await self.extract_members():
                    self.save_to_csv()
                    self.generate_sql_file()
                    console.print("\n[green]✅ Files saved successfully![/green]")
                    
            elif choice == "2":
                # Extract and import
                if not self.setup_supabase():
                    console.print("[yellow]Falling back to file export only...[/yellow]")
                    if await self.extract_members():
                        self.save_to_csv()
                        self.generate_sql_file()
                else:
                    if await self.extract_members():
                        # Always save backup
                        self.save_to_csv()
                        
                        # Try import
                        if await self.import_to_supabase():
                            console.print("\n[bold green]✅ Success! Members imported to whitelist[/bold green]")
                        else:
                            console.print("[yellow]Import failed. SQL file generated for manual import.[/yellow]")
                            self.generate_sql_file()
            
            return True
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    extractor = MemberExtractor()
    success = await extractor.run()
    
    if success:
        console.print("\n[bold green]🎉 Operation completed successfully![/bold green]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. If not auto-imported, run the SQL file in Supabase")
        console.print("2. Deploy your bot with: railway up")
        console.print("3. Existing members will have free access")
        console.print("4. New members will need to pay")
    else:
        console.print("\n[red]Operation failed or was cancelled[/red]")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)
