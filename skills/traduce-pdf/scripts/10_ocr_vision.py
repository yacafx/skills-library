#!/usr/bin/env python3
"""10_ocr_vision.py — OCR con Apple Vision (VNRecognizeTextRequest, modo accurate).
Uso: venv/bin/python 10_ocr_vision.py <img1> [img2 ...] --out <dir>
Salida: <dir>/<nombre>.vision.json  {page_file, w, h, lines:[{t,x,y,w,h,c}]}  (y desde ARRIBA, coords en px)
"""
import sys, os, json
import Quartz
import Vision
from Foundation import NSURL

def ocr(path):
    url = NSURL.fileURLWithPath_(path)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    W = Quartz.CGImageGetWidth(cg); H = Quartz.CGImageGetHeight(cg)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    req.setRecognitionLanguages_(["en-US"])
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision error: {err}")
    lines = []
    for obs in req.results():
        cand = obs.topCandidates_(1)[0]
        bb = obs.boundingBox()  # normalizado, origen abajo-izquierda
        x = bb.origin.x * W
        y = (1.0 - bb.origin.y - bb.size.height) * H
        w = bb.size.width * W
        h = bb.size.height * H
        lines.append({"t": str(cand.string()), "x": round(x,1), "y": round(y,1),
                      "w": round(w,1), "h": round(h,1), "c": round(float(obs.confidence()),3)})
    lines.sort(key=lambda l: (l["y"], l["x"]))
    return {"page_file": os.path.basename(path), "w": W, "h": H, "lines": lines}

if __name__ == "__main__":
    args = sys.argv[1:]
    out = "."
    if "--out" in args:
        i = args.index("--out"); out = args[i+1]; args = args[:i] + args[i+2:]
    os.makedirs(out, exist_ok=True)
    for p in args:
        r = ocr(p)
        name = os.path.splitext(os.path.basename(p))[0]
        dst = os.path.join(out, name + ".vision.json")
        json.dump(r, open(dst, "w"), ensure_ascii=False)
        print(f"{name}: {len(r['lines'])} líneas -> {dst}")
