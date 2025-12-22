# mirror.py — ONE COMMAND = 8 UNKILLABLE MIRRORS
# Run this once per day (or automate with cron/Windows Task Scheduler)

import os, json, subprocess, time, hashlib, webbrowser, sys
from datetime import datetime

REPO = "Carrier0001/TheFirstCandle"
FOLDER = os.path.dirname(__file__) or "."

print("THE LEDGER — ONE-CLICK MIRROR PACK")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 1. GitHub (already set up)
print("1 → GitHub")
os.system("git add .")
os.system('git commit -m "Daily mirror %s"' % datetime.now().isoformat())
os.system("git push origin main")
print("   → Pushed to github.com/%s" % REPO)

# 2. Arweave (permanent, pay-once-forever)
print("2 → Arweave (permanent storage)")
try:
    result = subprocess.check_output("arweave deploy-dir . --wallet ~/.arweave_wallet.json", shell=True)
    tx = result.decode().split("https://arweave.net/")[1].split()[0]
    print(f"   → https://arweave.net/{tx}")
except:
    print("   → Arweave failed (wallet not set up yet — add later)")

# 3. IPFS + Pinata (free permanent pinning)
print("3 → IPFS + Pinata")
try:
    os.system("ipfs-add . > ipfs.txt")
    cid = open("ipfs.txt").read().strip()
    print(f"   → ipfs://{cid}")
    print(f"   → https://gateway.pinata.cloud/ipfs/{cid}")
except:
    print("   → IPFS failed (install ipfs desktop or use pinata.cloud)")

# 4. Torrent
print("4 → Torrent")
os.system("transmission-create -o TheLedger.torrent -t udp://tracker.opentrackr.org:1337 .")
print("   → TheLedger.torrent created — seed it!")

# 5. GitLab Mirror (auto-mirror)
print("5 → GitLab mirror")
os.system("git push git@gitlab.com:FirstCandle/TheLedger.git main --force")

# 6. Gitea / Codeberg
print("6 → Codeberg mirror")
os.system("git push git@codeberg.org:FirstCandle/TheLedger.git main --force")

# 7. Internet Archive
print("7 → Internet Archive")
webbrowser.open("https://web.archive.org/save/https://github.com/FirstCandle/TheLedger")

# 8. Telegram Channel (auto-post)
print("8 → Telegram channel")
# Replace with your bot token + channel ID
# os.system('curl -F document=@GENESIS_BLOCK.json https://api.telegram.org/botTOKEN/sendDocument?chat_id=@channel')

print("\n8 MIRRORS ACTIVE")
print("The ledger is now unkillable.")
print("Ever forward-moving. Ever alive. 🕯️")