import os
import json
import mss
import numpy as np
import cv2

def load_config():
    path = os.path.join(os.path.dirname(__file__), 'config_fishing.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def draw_rect(img, rect, color=(0,255,0), label=None):
    if not rect or rect.get('w',0) <=0 or rect.get('h',0) <=0:
        return
    x, y, w, h = rect['x'], rect['y'], rect['w'], rect['h']
    cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
    if label:
        cv2.putText(img, label, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

def main():
    cfg = load_config()
    cap = cfg.get('capture_region', {})
    areas = cfg.get('areas', {})
    name_roi = cfg.get('result_name_roi', {})
    msg_roi  = cfg.get('result_message_roi', {})

    sct = mss.mss()
    frame = np.array(sct.grab(cap))

    # Dibujar áreas
    preview = frame.copy()
    draw_rect(preview, areas.get('wait'), (0,255,255), 'wait')
    draw_rect(preview, areas.get('e'), (0,255,0), 'e')
    draw_rect(preview, areas.get('r'), (0,128,255), 'r')
    draw_rect(preview, areas.get('t'), (255,128,0), 't')
    draw_rect(preview, name_roi, (255,0,255), 'name')
    draw_rect(preview, msg_roi, (255,255,0), 'message')

    out_path = os.path.join(os.path.dirname(__file__), 'preview_capture.png')
    cv2.imwrite(out_path, preview)
    print(f"Guardado: {out_path}")
    print("Abre la imagen y ajusta x,y,w,h en result_name_roi/result_message_roi si hace falta.")

if __name__ == '__main__':
    main()
