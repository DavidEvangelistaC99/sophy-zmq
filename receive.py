# receiver.py

import zmq
from pathlib import Path
import digital_rf

DEST = Path("/home/david/Documents/DATA_R/CHIRP_DP@2025-12-11T15-20-07/rawdata")

context = zmq.Context()
socket = context.socket(zmq.PULL)

socket.connect("tcp://localhost:5555")

print("Esperando datos...")

while True:

    msg = socket.recv_json()

    if "END" in msg:
        print("\nTRANSFERENCIA COMPLETADA")
        break

    relpath = msg["relpath"]
    data = bytes.fromhex(msg["data"])

    filepath = DEST / relpath

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(data)

    print("RECIBIDO:", relpath)

# ==========================================================
# VERIFICAR DIGITAL RF
# ==========================================================

print("\nVerificando DigitalRF...")

try:

    drf = digital_rf.DigitalRFReader(str(DEST))

    channels = drf.get_channels()

    print("Canales encontrados:")
    print(channels)

except Exception as e:

    print("ERROR leyendo DigitalRF:")
    print(e)

print("\nReceiver finalizado.")