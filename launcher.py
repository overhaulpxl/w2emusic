import subprocess
import os
import sys
import time
from dotenv import dotenv_values

print("="*50)
print("Memulai W2E Bot Cluster Manager")
print("="*50)

# Pastikan path eksekusi python sesuai dengan environment
python_exe = sys.executable

# Load variables dari file .env masing-masing
basic_env = dotenv_values(".env") or {}
premium_env = dotenv_values("premium_bot/.env") or {}

processes = []

print("\n--- Menyiapkan Basic Bots ---")
for i in range(1, 6):
    token = basic_env.get(f'BASIC_TOKEN_{i}')
    prefix = basic_env.get(f'BASIC_PREFIX_{i}', f'w{i}!')
    
    if token and token != "your_bot_token_here":
        env = os.environ.copy()
        env['DISCORD_TOKEN'] = token
        env['BOT_PREFIX'] = prefix
        
        print(f"[STARTING] Basic Bot {i} (Prefix: {prefix})")
        # Run bot.py di root directory
        p = subprocess.Popen([python_exe, "bot.py"], env=env, cwd=os.getcwd())
        processes.append(('Basic', i, p, prefix))
    else:
        print(f"[SKIPPED] Basic Bot {i} - Token belum diatur di .env")

print("\n--- Menyiapkan Premium Bots ---")
for i in range(1, 6):
    token = premium_env.get(f'PREMIUM_TOKEN_{i}')
    prefix = premium_env.get(f'PREMIUM_PREFIX_{i}', f'p{i}!')
    
    if token and token != "your_bot_token_here":
        env = os.environ.copy()
        env['DISCORD_TOKEN'] = token
        env['BOT_PREFIX'] = prefix
        
        # Pass Spotify credentials if available
        if premium_env.get('SPOTIFY_CLIENT_ID'):
            env['SPOTIFY_CLIENT_ID'] = premium_env.get('SPOTIFY_CLIENT_ID')
        if premium_env.get('SPOTIFY_CLIENT_SECRET'):
            env['SPOTIFY_CLIENT_SECRET'] = premium_env.get('SPOTIFY_CLIENT_SECRET')
            
        print(f"[STARTING] Premium Bot {i} (Prefix: {prefix})")
        # Run bot.py di dalam premium_bot directory
        premium_dir = os.path.join(os.getcwd(), 'premium_bot')
        p = subprocess.Popen([python_exe, "bot.py"], env=env, cwd=premium_dir)
        processes.append(('Premium', i, p, prefix))
    else:
        print(f"[SKIPPED] Premium Bot {i} - Token belum diatur di premium_bot/.env")

print("\n" + "="*50)
if processes:
    print(f"Total {len(processes)} bot berhasil diluncurkan!")
    print("Tekan Ctrl+C di terminal ini untuk mematikan semua bot sekaligus.")
    print("="*50 + "\n")
    
    try:
        while True:
            time.sleep(1)
            # Mengecek apakah ada proses bot yang mati / crash
            for i in range(len(processes)):
                type_bot, bot_num, p, prefix = processes[i]
                if p.poll() is not None:
                    print(f"⚠️ [{type_bot} Bot {bot_num}] TERHENTI! (Kode Exit: {p.returncode})")
                    # TODO: Jika ingin auto-restart bisa ditambahkan disini
                    processes[i] = (type_bot, bot_num, p, prefix) # Just placeholder
    except KeyboardInterrupt:
        print("\n[!] Menerima perintah berhenti (Ctrl+C). Mematikan semua bot...")
        for type_bot, bot_num, p, prefix in processes:
            p.terminate()
        print("Semua bot telah dimatikan.")
else:
    print("Tidak ada bot yang diluncurkan. Pastikan token sudah diisi di .env!")
    print("="*50 + "\n")
