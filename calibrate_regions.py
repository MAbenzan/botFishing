import json
import os
import mss
import numpy as np
import cv2

sct = mss.mss()
monitor = sct.monitors[1]
capture_region = None
areas = {'wait': None, 'e': None, 'r': None, 't': None, 'name': None, 'message': None, 'icon': None}
selection_mode = None
dragging = False
start_pt = None
current_rect = None
baseline = {}
active_green = {}
active_red_wait = None

def rect_to_xywh(x1, y1, x2, y2):
    x = x1 if x1 < x2 else x2
    y = y1 if y1 < y2 else y2
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    return x, y, w, h

def mouse_cb(event, x, y, flags, param):
    global dragging, start_pt, current_rect, selection_mode, capture_region, areas
    if selection_mode is None:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        dragging = True
        start_pt = (x, y)
        current_rect = (x, y, x, y)
    elif event == cv2.EVENT_MOUSEMOVE and dragging:
        current_rect = (start_pt[0], start_pt[1], x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
        current_rect = (start_pt[0], start_pt[1], x, y)
        x1, y1, x2, y2 = current_rect
        if selection_mode == 'capture':
            gx, gy, gw, gh = rect_to_xywh(x1, y1, x2, y2)
            capture_region = {'top': gy + monitor['top'], 'left': gx + monitor['left'], 'width': gw, 'height': gh}
            selection_mode = None
        else:
            if capture_region is None:
                selection_mode = None
                return
            rx, ry, rw, rh = rect_to_xywh(x1, y1, x2, y2)
            areas[selection_mode] = {'x': rx, 'y': ry, 'w': rw, 'h': rh}
            selection_mode = None

def draw_overlay(img, rect, color=(0, 255, 255)):
    if rect is None:
        return
    x1, y1, x2, y2 = rect
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

def put_text(img, text, y=20, color=(0, 0, 0)):
    # Borde blanco para contraste
    cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 3)
    # Texto negro (o el color que pases)
    cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

def main():
    global capture_region, selection_mode, current_rect
    cv2.namedWindow("Calibrador")
    cv2.setMouseCallback("Calibrador", mouse_cb)

    while True:
        frame = np.array(sct.grab(monitor))
        if capture_region is None or selection_mode == 'capture':
            display = frame.copy()
            if capture_region is not None:
                x = capture_region['left'] - monitor['left']
                y = capture_region['top'] - monitor['top']
                w = capture_region['width']
                h = capture_region['height']
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            put_text(display, "GLOBAL | C: caja grande | Q: salir | S: guardar")
        else:
            x = capture_region['left'] - monitor['left']
            y = capture_region['top'] - monitor['top']
            w = capture_region['width']
            h = capture_region['height']
            roi = frame[y:y + h, x:x + w].copy()
            display = roi
            put_text(display, "ROI | W/E/R/T: áreas | N: nombre | M: mensaje | I: icono | S: guardar | Q: salir")
            for name, rect in areas.items():
                if rect:
                    cv2.rectangle(display, (rect['x'], rect['y']), (rect['x'] + rect['w'], rect['y'] + rect['h']), (0, 255, 0), 2)
                    cv2.putText(display, name, (rect['x'], rect['y'] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        draw_overlay(display, current_rect, (255, 255, 0))
        cv2.imshow("Calibrador", display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('c'):
            selection_mode = 'capture'
            current_rect = None
        elif key == ord('w'):
            selection_mode = 'wait' if capture_region is not None else None
            current_rect = None
        elif key == ord('e'):
            selection_mode = 'e' if capture_region is not None else None
            current_rect = None
        elif key == ord('r'):
            selection_mode = 'r' if capture_region is not None else None
            current_rect = None
        elif key == ord('t'):
            selection_mode = 't' if capture_region is not None else None
            current_rect = None
        elif key == ord('i'):
            selection_mode = 'icon' if capture_region is not None else None
            current_rect = None
        elif key == ord('n'):
            selection_mode = 'name' if capture_region is not None else None
            current_rect = None
        elif key == ord('m'):
            selection_mode = 'message' if capture_region is not None else None
            current_rect = None
        elif key == ord('b'):
            if capture_region is None:
                continue
            x = capture_region['left'] - monitor['left']
            y = capture_region['top'] - monitor['top']
            w = capture_region['width']
            h = capture_region['height']
            acc = {}
            cnt = 0
            for _ in range(120):
                frame2 = np.array(sct.grab(monitor))
                roi2 = frame2[y:y + h, x:x + w]
                for name, rect in areas.items():
                    if not rect:
                        continue
                    rroi = roi2[rect['y']:rect['y'] + rect['h'], rect['x']:rect['x'] + rect['w']]
                    if rroi.size == 0:
                        continue
                    bgrA = np.mean(rroi, axis=(0, 1))
                    g = bgrA[1]
                    r = bgrA[2]
                    if name not in acc:
                        acc[name] = {'g': 0.0, 'r': 0.0}
                    acc[name]['g'] += g
                    acc[name]['r'] += r
                cnt += 1
            for name in acc:
                baseline[name] = {'g': acc[name]['g'] / cnt, 'r': acc[name]['r'] / cnt}
        elif key == ord('g'):
            if capture_region is None:
                continue
            x = capture_region['left'] - monitor['left']
            y = capture_region['top'] - monitor['top']
            w = capture_region['width']
            h = capture_region['height']
            acc = {}
            cnt = 0
            for _ in range(90):
                frame2 = np.array(sct.grab(monitor))
                roi2 = frame2[y:y + h, x:x + w]
                for name in ['e', 'r', 't']:
                    rect = areas.get(name)
                    if not rect:
                        continue
                    rroi = roi2[rect['y']:rect['y'] + rect['h'], rect['x']:rect['x'] + rect['w']]
                    if rroi.size == 0:
                        continue
                    bgrA = np.mean(rroi, axis=(0, 1))
                    g = bgrA[1]
                    if name not in acc:
                        acc[name] = {'g': 0.0}
                    acc[name]['g'] += g
                cnt += 1
            for name in acc:
                active_green[name] = {'g': acc[name]['g'] / cnt}
        elif key == ord('r'):
            if capture_region is None:
                continue
            rect = areas.get('wait')
            if not rect:
                continue
            x = capture_region['left'] - monitor['left']
            y = capture_region['top'] - monitor['top']
            w = capture_region['width']
            h = capture_region['height']
            acc_r = 0.0
            cnt = 0
            for _ in range(90):
                frame2 = np.array(sct.grab(monitor))
                roi2 = frame2[y:y + h, x:x + w]
                rroi = roi2[rect['y']:rect['y'] + rect['h'], rect['x']:rect['x'] + rect['w']]
                if rroi.size == 0:
                    continue
                bgrA = np.mean(rroi, axis=(0, 1))
                acc_r += bgrA[2]
                cnt += 1
            if cnt > 0:
                active_red_wait = acc_r / cnt
        elif key == ord('s'):
            if capture_region is None:
                continue
            
            green_candidates = []
            # Cargar config existente para preservar umbrales manuales
            existing_config = {}
            if os.path.exists("config_fishing.json"):
                try:
                    with open("config_fishing.json", "r") as f:
                        existing_config = json.load(f)
                except:
                    pass

            # Usar umbrales existentes o valores por defecto seguros
            final_thresholds = existing_config.get('thresholds', {
                'green_min': 140,
                'red_min': 160,
                'wait_green_diff_min': 10,
                'wait_red_diff_min': 15,
                'green_diff_min': 30,
                'letter_red_diff_min': 15
            })

            # Si se calcularon nuevos umbrales por el proceso de calibración de color (teclas B/G), usarlos
            if active_green:
                for v in active_green.values():
                    if 'g' in v:
                        green_candidates.append(v['g'])
            
            if green_candidates:
                 final_thresholds['green_min'] = int(min(green_candidates))
            
            wait_base = baseline.get('wait', {})
            if 'r' in wait_base and active_red_wait is not None:
                 final_thresholds['red_min'] = int((wait_base['r'] + active_red_wait) / 2.0)

            cfg = {
                'capture_region': capture_region,
                'areas': {k: v for k, v in areas.items() if k in ['wait','e','r','t'] and v is not None},
                'thresholds': final_thresholds,
                'keys': ['e', 'r', 't'],
                'result_name_roi': areas.get('name') or existing_config.get('result_name_roi') or {'x': 0, 'y': 0, 'w': 0, 'h': 0},
                'result_message_roi': areas.get('message') or existing_config.get('result_message_roi') or {'x': 0, 'y': 0, 'w': 0, 'h': 0},
                'fishing_icon_roi': areas.get('icon') or existing_config.get('fishing_icon_roi') or {'x': 0, 'y': 0, 'w': 0, 'h': 0},
                'use_prediction': existing_config.get('use_prediction', True),
                'start_key': existing_config.get('start_key', '5'),
                'start_press_on_run': existing_config.get('start_press_on_run', True),
                'start_focus_delay_seconds': existing_config.get('start_focus_delay_seconds', 4),
                'log_event_details': existing_config.get('log_event_details', False),
                'log_debug_values': existing_config.get('log_debug_values', False)
            }
            with open("config_fishing.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            
            print("\n" + "="*40)
            print("   ¡CONFIGURACIÓN GUARDADA CORRECTAMENTE!")
            print("   Archivo: config_fishing.json actualizado")
            print("-" * 30)
            print("REGIONES GUARDADAS EXITOSAMENTE:")
            print(f"  Wait (Barra): {areas.get('wait') or 'No definida'}")
            print(f"  E: {areas.get('e') or 'No definida'}")
            print(f"  R: {areas.get('r') or 'No definida'}")
            print(f"  T: {areas.get('t') or 'No definida'}")
            print(f"  Icono pesca: {areas.get('icon') or 'No definido'}")
            print("="*40 + "\n")
            
            # Feedback visual temporal (hack simple: dibujar texto y esperar un poco)
            temp_display = display.copy()
            put_text(temp_display, "!!! GUARDADO !!!", y=60, color=(0, 0, 255))
            cv2.imshow("Calibrador", temp_display)
            cv2.waitKey(500) # Mostrar mensaje por 0.5 segundos

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
