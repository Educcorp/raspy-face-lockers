#!/usr/bin/env python3
"""
Download face detection and recognition models.

Modelos:
  1. OpenCV DNN SSD – detección de rostros (Caffe)
  2. dlib shape_predictor_68 – landmarks faciales (68 puntos)
  3. dlib face_recognition_resnet_v1 – embeddings 128-dim

Uso: python download_models.py
"""

import os
import bz2
import urllib.request
from pathlib import Path
import sys

def download_file(url: str, filepath: str) -> bool:
    """Download a file with progress tracking."""
    filename = Path(filepath).name
    print(f"Descargando {filename}...")
    print(f"  URL: {url}")
    
    try:
        def show_progress(block_num, block_size, total_size):
            """Show download progress."""
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
            bar_length = 40
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r  [{bar}] {percent:.1f}%", end="", flush=True)
        
        urllib.request.urlretrieve(url, filepath, show_progress)
        print("\n  ✓ Descarga completada")
        return True
    except Exception as e:
        print(f"\n  ✗ Error: {e}")
        return False


def main():
    """Download all required models."""
    project_root = Path(__file__).parent
    models_dir = project_root / "assets" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("  DESCARGADOR DE MODELOS - SMART LOCKER")
    print("="*60 + "\n")
    
    # Face detection models (SSD ResNet)
    # Source: https://github.com/opencv/opencv_3rdparty/tree/dnn_samples_face_detector_20170830
    models = {
        "deploy.prototxt": (
            "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
            "dnn_samples_face_detector_20170830/"
            "opencv_face_detector.prototxt"
        ),
        "res10_300x300_ssd_iter_140000.caffemodel": (
            "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
            "dnn_samples_face_detector_20170830/"
            "res10_300x300_ssd_iter_140000.caffemodel"
        ),
    }
    
    # dlib models (compressed with bz2)
    dlib_models = {
        "shape_predictor_68_face_landmarks.dat": (
            "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2",
            95,
        ),
        "dlib_face_recognition_resnet_model_v1.dat": (
            "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2",
            22,
        ),
    }

    print("Modelos requeridos:")

    # OpenCV DNN models
    for filename, url in models.items():
        filepath = models_dir / filename
        size_mb = 27 if "caffemodel" in filename else 0.08
        print(f"\n  • {filename} (~{size_mb} MB)")
        
        if filepath.exists():
            print(f"    ✓ Ya existe")
        else:
            if not download_file(url, str(filepath)):
                print(f"\n  Nota: Puedes descargar manualmente desde:")
                print(f"    {url}")
                print(f"  Y guardar en: {filepath}")
                continue

    # dlib models (need bz2 decompression)
    for filename, (url, size_mb) in dlib_models.items():
        filepath = models_dir / filename
        print(f"\n  • {filename} (~{size_mb} MB)")
        
        if filepath.exists():
            print(f"    ✓ Ya existe")
        else:
            bz2_path = str(filepath) + ".bz2"
            if not download_file(url, bz2_path):
                print(f"\n  Nota: Puedes descargar manualmente desde:")
                print(f"    {url}")
                print(f"  Y guardar en: {filepath}")
                continue
            print(f"    Descomprimiendo...")
            try:
                with open(bz2_path, "rb") as f_in:
                    data = bz2.decompress(f_in.read())
                with open(str(filepath), "wb") as f_out:
                    f_out.write(data)
                os.remove(bz2_path)
                print(f"    ✓ Descomprimido ({len(data)/1024/1024:.1f} MB)")
            except Exception as e:
                print(f"    ✗ Error descomprimiendo: {e}")
    
    # Verify
    print("\n" + "="*60)
    print("  VERIFICACIÓN")
    print("="*60)
    
    all_ok = True
    all_files = list(models.keys()) + list(dlib_models.keys())
    for filename in all_files:
        filepath = models_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / (1024*1024)
            print(f"✓ {filename:.<50} {size:>6.1f} MB")
        else:
            print(f"✗ {filename:.<50} FALTA")
            all_ok = False
    
    print("\n" + "="*60)
    if all_ok:
        print("✓ Todos los modelos están disponibles")
    else:
        print("✗ Algunos modelos no se pudieron descargar")
        print("\nInstrucciones:")
        print("1. Descarga los archivos manualmente desde las URLs anteriores")
        print(f"2. Guárdalos en: {models_dir}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
