#!/usr/bin/env python3
"""70_lama.py — inpainting LaMa directo con torch (sin iopaint; su pin de Pillow
viejo no compila en Pythons modernos). Carga el checkpoint TorchScript big-lama.

Uso como módulo:  from importlib... lama = Lama(); out = lama.inpaint(img_pil, mask_pil)
Uso CLI (humo):   venv/bin/python 70_lama.py imagen.png mascara.png salida.png
La máscara: blanco (255) = zona a reconstruir, negro = conservar.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

P = Path(__file__).resolve().parent.parent
CKPT = P / "plantillas" / "modelos" / "big-lama.pt"


class Lama:
    def __init__(self, device=None):
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = torch.jit.load(str(CKPT), map_location="cpu").eval().to(self.device)

    @staticmethod
    def _pad8(arr):
        h, w = arr.shape[:2]
        ph, pw = (8 - h % 8) % 8, (8 - w % 8) % 8
        if arr.ndim == 3:
            return np.pad(arr, ((0, ph), (0, pw), (0, 0)), mode="reflect")
        return np.pad(arr, ((0, ph), (0, pw)), mode="reflect")

    @torch.inference_mode()
    def inpaint(self, img: Image.Image, mask: Image.Image) -> Image.Image:
        rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
        m = (np.asarray(mask.convert("L"), dtype=np.float32) > 127).astype(np.float32)
        h, w = rgb.shape[:2]
        rgb_p, m_p = self._pad8(rgb), self._pad8(m)
        t_img = torch.from_numpy(rgb_p).permute(2, 0, 1).unsqueeze(0).to(self.device)
        t_mask = torch.from_numpy(m_p).unsqueeze(0).unsqueeze(0).to(self.device)
        out = self.model(t_img, t_mask)[0].permute(1, 2, 0).cpu().numpy()
        out = np.clip(out * 255.0, 0, 255).astype(np.uint8)[:h, :w]
        # conservar píxeles originales fuera de la máscara
        m3 = np.repeat(m[:h, :w, None], 3, axis=2)
        final = (out * m3 + np.asarray(img.convert("RGB")) * (1 - m3)).astype(np.uint8)
        return Image.fromarray(final)


if __name__ == "__main__":
    img, mask, salida = sys.argv[1], sys.argv[2], sys.argv[3]
    lama = Lama()
    print(f"LaMa en {lama.device}")
    res = lama.inpaint(Image.open(img), Image.open(mask))
    res.save(salida)
    print(f"✓ {salida}")
