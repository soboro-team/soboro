# Tacotron
import os, torch, json
from jamo import hangul_to_jamo
from tacotron_eval import Synthesizer
# MelGan
import soundfile as sf
from os import path
from gan import Generator
from melgan_eval import find_endpoint
# Fast API
from fastapi import FastAPI
import uvicorn

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
app = FastAPI()

idx = 0

@app.on_event("startup") 
def startup_event(): 
    print("Startup event") 
    global idx
    idx = 0

def return_idx():
    global idx
    while True:
        idx += 1
        yield idx

@app.get("/tts/{text}")
def tts(text: str):
    with open("config.json") as f:
        data = f.read()
    config = json.loads(data)
    save_dir = config["save_dir"]
    load_dir = config["load_dir"]
    ckpt = config["ckpt"]
    # parameter
    device = "cuda" if torch.cuda.is_available() else "cpu"
    valid_file_path = save_dir+"/"+text

    # distinct
    if path.exists(valid_file_path):
        with open(valid_file_path, "r") as f:
            filename = f.readline()
        return {"filename": "{}".format(filename)}
    
    # taco-eval
    synth = Synthesizer()
    synth.load(ckpt)
    jamo = "".join(list(hangul_to_jamo(text)))
    mel = synth.synthesize(jamo)
    vocoder = Generator(80)
    ckpt = torch.load(load_dir, map_location=device)
    vocoder.load_state_dict(ckpt["G"])
    mel = mel.unsqueeze(0)

    # melgan-eval
    g_audio = vocoder(mel)
    g_audio = g_audio.squeeze().cpu()
    audio = (g_audio.detach().numpy() * 32768)
    audio = audio[:find_endpoint(audio)]
    filename = "generated_{}.wav".format(next(return_idx()))
    filepath = path.join(save_dir, filename)
    response = {"filename": "{}".format(filename)}
    with open(filepath, 'wb') as f:
        sf.write(f, audio.astype("int16"), 22050)
    val_filepath = path.join(valid_file_path, filename)
    with open(val_filepath, "wb") as f:
        f.write(f)
    os.chmod(path.join(filepath, filename), 0o755)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=13579)