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

processes = []

print("\n--- Menyiapkan Basic Bots ---")
for i in range(1, 2):
    token = basic_env.get(f'BASIC_TOKEN_{i}')
    prefix = basic_env.get(f'BASIC_PREFIX_{i}', f'w{i}!')
    
    if token and token != "your_bot_token_here":
        env = os.environ.copy()
        env['DISCORD_TOKEN'] = token
        env['BOT_PREFIX'] = prefix
        
        print(f"[STARTING] Basic Bot {i} (Prefix: {prefix})")
        # Run bot.py di root directory
        p = subprocess.Popen([python_exe, "bot.py"], env=env, cwd=os.getcwd())
        # FIX: Store env in a dictionary to support non-blocking restarts
        processes.append({
            'type_bot': 'Basic', 
            'bot_num': i, 
            'p': p, 
            'prefix': prefix, 
            'env': env,
            'restart_after': 0
        })
    else:
        print(f"[SKIPPED] Basic Bot {i} - Token belum diatur di .env")


print("\n" + "="*50)
if processes:
    print(f"Total {len(processes)} bot berhasil diluncurkan!")
    print("Tekan Ctrl+C di terminal ini untuk mematikan semua bot sekaligus.")
    print("="*50 + "\n")
    
    try:
        while True:
            time.sleep(1)
            current_time = time.time()
            
            # Mengecek apakah ada proses bot yang mati / crash
            for bot_data in processes:
                p = bot_data['p']
                
                # Check if it needs a restart and timer is up
                if p is None:
                    if current_time >= bot_data['restart_after']:
                        print(f"[*] Merestart {bot_data['type_bot']} Bot {bot_data['bot_num']}...")
                        new_p = subprocess.Popen([python_exe, "bot.py"], env=bot_data['env'], cwd=os.getcwd())
                        bot_data['p'] = new_p
                    continue
                    
                if p.poll() is not None:
                    print(f"[!] [{bot_data['type_bot']} Bot {bot_data['bot_num']}] TERHENTI! (Kode Exit: {p.returncode})")
                    print(f"[*] Menjadwalkan restart dalam 3 detik (Non-blocking)...")
                    bot_data['p'] = None
                    bot_data['restart_after'] = current_time + 3.0
                    
    except KeyboardInterrupt:
        print("\n[!] Menerima perintah berhenti (Ctrl+C). Mematikan semua bot...")
        for bot_data in processes:
            p = bot_data['p']
            if p is not None:
                p.terminate()
        print("Semua bot telah dimatikan.")
else:
    print("Tidak ada bot yang diluncurkan. Pastikan token sudah diisi di .env!")
    print("="*50 + "\n")
