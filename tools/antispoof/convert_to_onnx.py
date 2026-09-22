#!/usr/bin/env python3
"""
Convierte los pesos .pth de Silent-Face-Anti-Spoofing (minivision-ai,
Apache-2.0) a ONNX, para correrlos con onnxruntime en vez de PyTorch
completo — más liviano para el Pi y para el runtime del panel web.

Esto se corre UNA SOLA VEZ en una máquina de desarrollo (requiere torch,
que NO es dependencia del proyecto). El resultado (dos archivos .onnx
pequeños, ~1-2 MB cada uno) se versiona directamente en assets/models/.

Uso:
    python tools/antispoof/convert_to_onnx.py \
        --pth-dir /ruta/a/los/pth/originales \
        --out-dir assets/models

Los .pth originales (no incluidos en este repo por ser artefactos de
PyTorch, no del proyecto) se descargan de:
    https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/master/resources/anti_spoof_models
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from minifasnet import MiniFASNetV1, MiniFASNetV1SE, MiniFASNetV2, MiniFASNetV2SE

MODEL_MAPPING = {
    "MiniFASNetV1": MiniFASNetV1,
    "MiniFASNetV2": MiniFASNetV2,
    "MiniFASNetV1SE": MiniFASNetV1SE,
    "MiniFASNetV2SE": MiniFASNetV2SE,
}


def parse_model_name(model_name: str):
    """Idéntico a src/utility.py del repo original: extrae tamaño de
    entrada, tipo de modelo y scale de crop a partir del nombre de archivo."""
    info = model_name.split("_")[0:-1]
    h_input, w_input = info[-1].split("x")
    model_type = model_name.split(".pth")[0].split("_")[-1]
    scale = None if info[0] == "org" else float(info[0])
    return int(h_input), int(w_input), model_type, scale


def get_kernel(height: int, width: int) -> tuple[int, int]:
    return (height + 15) // 16, (width + 15) // 16


def convert_one(pth_path: Path, out_dir: Path) -> None:
    h_input, w_input, model_type, scale = parse_model_name(pth_path.name)
    kernel_size = get_kernel(h_input, w_input)

    model = MODEL_MAPPING[model_type](conv6_kernel=kernel_size)
    state_dict = torch.load(pth_path, map_location="cpu", weights_only=True)

    # Los checkpoints originales a veces vienen de entrenamiento con
    # DataParallel, con prefijo "module." en cada clave.
    first_key = next(iter(state_dict))
    if first_key.startswith("module."):
        state_dict = {k[len("module."):]: v for k, v in state_dict.items()}
    model.load_state_dict(state_dict)
    model.eval()

    dummy = torch.randn(1, 3, h_input, w_input, dtype=torch.float32)
    out_path = out_dir / pth_path.with_suffix(".onnx").name

    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        input_names=["input"],
        output_names=["logits"],
        opset_version=18,
        dynamic_axes=None,  # tamaño de entrada fijo: 1x3xHxW
    )
    print(f"✓ {pth_path.name} -> {out_path.name}  "
          f"(scale={scale}, kernel={kernel_size}, size={w_input}x{h_input})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pth-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pth_files = sorted(args.pth_dir.glob("*.pth"))
    if not pth_files:
        raise SystemExit(f"No se encontraron .pth en {args.pth_dir}")

    for pth_path in pth_files:
        convert_one(pth_path, args.out_dir)


if __name__ == "__main__":
    main()
