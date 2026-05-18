# sender.py

import zmq
import os
import time
import argparse
from pathlib import Path

# ==========================================================
# ARGPARSE
# ==========================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--continuous",
    type=bool
)

args = parser.parse_args()

# ==========================================================
# CONFIGURACION
# ==========================================================

RAWDATA = Path("/home/david/Documents/DATA/CHIRP_DP@2025-12-11T15-20-07/rawdata")

channels = ["ch0", "ch1"]

# True  -> monitoreo infinito (THOR realtime)
# False -> dataset finito y termina solo
CONTINUOUS = args.continuous

# cuantos ciclos vacios esperar antes de terminar

IDLE_LIMIT = 20

# tiempo entre scans
SCAN_DELAY = 0.2

# ==========================================================
# ZMQ
# ==========================================================

context = zmq.Context()

socket = context.socket(zmq.PUSH)

socket.bind("tcp://*:5555")

print("Esperando receiver...")
time.sleep(2)

# ==========================================================
# CONTROL
# ==========================================================

sent_files = set()

# ==========================================================
# FUNCION ENVIO
# ==========================================================

def send_file(filepath):

    relpath = str(filepath.relative_to(RAWDATA))

    msg = {
        "relpath": relpath,
        "data": filepath.read_bytes().hex(),
    }

    socket.send_json(msg)

    print("ENVIADO:", relpath)

# ==========================================================
# EXTRAER TIMESTAMP
# ==========================================================

def extract_timestamp(filename):

    # rf@1765466419.000.h5

    s = filename.replace("rf@", "")
    s = s.replace(".h5", "")

    return float(s)

# ==========================================================
# 1. ENVIAR PROPIEDADES
# ==========================================================

print("\n===== ENVIANDO PROPIEDADES =====\n")

for ch in channels:

    files = [
        RAWDATA / ch / "drf_properties.h5",
        RAWDATA / ch / "metadata" / "dmd_properties.h5",
    ]

    for filepath in files:

        if filepath.exists():

            send_file(filepath)

            sent_files.add(str(filepath))

# ==========================================================
# 2. ENVIAR METADATA
# ==========================================================

print("\n===== ENVIANDO METADATA =====\n")

for ch in channels:

    meta_root = RAWDATA / ch / "metadata"

    metadata_files = []

    for root, dirs, files in os.walk(meta_root):

        for file in files:

            if file.startswith("metadata@"):

                metadata_files.append(Path(root) / file)

    metadata_files = sorted(metadata_files)

    for filepath in metadata_files:

        send_file(filepath)

        sent_files.add(str(filepath))

# ==========================================================
# 3. STREAM RF INTERCALADO
# ==========================================================

print("\n===== MONITOREANDO RF =====\n")

idle_counter = 0

while True:

    rf_candidates = []

    # ======================================================
    # BUSCAR NUEVOS RF
    # ======================================================

    for ch in channels:

        ch_root = RAWDATA / ch

        for root, dirs, files in os.walk(ch_root):

            for file in files:

                # solo rf finales
                if not file.startswith("rf@"):
                    continue

                if not file.endswith(".h5"):
                    continue

                # ignorar temporales
                if "tmp." in file:
                    continue

                filepath = Path(root) / file

                # evitar reenviar
                if str(filepath) in sent_files:
                    continue

                try:

                    ts = extract_timestamp(file)

                except Exception:

                    continue

                rf_candidates.append(
                    (
                        ts,
                        ch,
                        filepath
                    )
                )

    # ======================================================
    # ORDEN TEMPORAL GLOBAL
    # ======================================================

    rf_candidates.sort(
        key=lambda x: (x[0], x[1])
    )

    # ======================================================
    # ENVIAR INTERCALADO
    # ======================================================

    if len(rf_candidates) == 0:

        idle_counter += 1

    else:

        idle_counter = 0

        for ts, ch, filepath in rf_candidates:

            send_file(filepath)

            sent_files.add(str(filepath))

    # ======================================================
    # TERMINAR EN MODO FINITO
    # ======================================================

    if not CONTINUOUS:

        if idle_counter >= IDLE_LIMIT:

            print("\nDATASET COMPLETO")

            break

    time.sleep(SCAN_DELAY)

# ==========================================================
# FINALIZAR
# ==========================================================

socket.send_json({"END": True})

print("\nDONE")