import os
import shutil
from pathlib import Path
from datetime import datetime

# Directories
project_dir = Path.home() / "Downloads" / "Agent" / "Reconciliation"
agent_downloads = project_dir / "downloads"
mac_downloads = Path.home() / "Downloads"

print("=" * 80)
print("DIAGNOSTIC REPORT")
print("=" * 80)

# Check agent downloads folder
print(f"\n1. Agent downloads folder: {agent_downloads}")
print(f"   Exists: {agent_downloads.exists()}")

if agent_downloads.exists():
    files = list(agent_downloads.glob("*"))
    print(f"   Files count: {len(files)}")
    for f in files:
        print(f"   - {f.name} ({f.stat().st_size:,} bytes)")
else:
    print("   ❌ Folder doesn't exist!")
    agent_downloads.mkdir(parents=True, exist_ok=True)
    print("   ✓ Created folder")

# Check Mac Downloads folder for recent Excel files
print(f"\n2. Mac Downloads folder: {mac_downloads}")
recent_excel = []
for pattern in ["*.xlsx", "*.xls"]:
    for f in mac_downloads.glob(pattern):
        # Check if file was modified in last 2 hours
        mod_time = datetime.fromtimestamp(f.stat().st_mtime)
        age_minutes = (datetime.now() - mod_time).total_seconds() / 60
        if age_minutes < 120:  # Last 2 hours
            recent_excel.append((f, age_minutes))

print(f"   Recent Excel files (last 2 hours): {len(recent_excel)}")
for f, age in sorted(recent_excel, key=lambda x: x[1]):
    print(f"   - {f.name} ({f.stat().st_size:,} bytes, {int(age)} min ago)")

# Offer to move files
if recent_excel and len(list(agent_downloads.glob("*.xls*"))) == 0:
    print("\n" + "=" * 80)
    print("FOUND EXCEL FILES IN MAC DOWNLOADS!")
    print("=" * 80)
    print("\nThese files are likely your downloaded RMS files.")
    print("Moving them to agent downloads folder...\n")
    
    for f, age in recent_excel:
        dest = agent_downloads / f.name
        print(f"Moving: {f.name} -> downloads/")
        shutil.copy2(f, dest)
        print(f"   ✓ Copied successfully")
    
    print("\n✅ Files moved! Now the agent should find them.")

# Check EPF folder
print("\n" + "=" * 80)
epf_folder = project_dir / "epf_uploads"
print(f"3. EPF uploads folder: {epf_folder}")
print(f"   Exists: {epf_folder.exists()}")

if epf_folder.exists():
    epf_files = list(epf_folder.glob("*.xls*"))
    print(f"   EPF files: {len(epf_files)}")
    for f in epf_files:
        print(f"   - {f.name} ({f.stat().st_size:,} bytes)")
    
    if len(epf_files) == 0:
        print("\n   ⚠️  WARNING: No EPF file found!")
        print("   Please upload an EPF file to: epf_uploads/")
else:
    print("   ❌ Folder doesn't exist!")
    epf_folder.mkdir(parents=True, exist_ok=True)
    print("   ✓ Created folder")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
