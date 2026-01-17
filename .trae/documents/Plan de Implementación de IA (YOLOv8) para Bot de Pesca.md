# Plan de Implementación de IA (YOLOv8) para Bot de Pesca

Este plan transformará tu bot de un sistema "ciego" basado en coordenadas fijas a un sistema "inteligente" que ve y entiende la pantalla, eliminando la necesidad de calibración manual constante.

## Fase 1: Recolección y Preparación de Datos (La base de todo)
Antes de que la IA pueda pescar, necesita aprender qué es un pez, un botón o un icono.
1.  **Crear Dataset de Imágenes**:
    *   Necesitamos entre **100 y 300 capturas de pantalla** del juego en diferentes situaciones:
        *   Esperando (con icono de pesca visible).
        *   Minijuego activo (con letras E, R, T visibles en verde y rojo).
        *   Final de pesca (con nombre del pez).
    *   *Acción*: Crearemos un pequeño script (`capture_data.py`) que tome una foto cada 2 segundos mientras juegas o mientras el bot actual funciona, guardándolas en una carpeta `dataset/images`.
2.  **Etiquetado (Labeling)**:
    *   Usar una herramienta gratuita como **LabelImg** o **Roboflow** (web).
    *   Dibujar cajas alrededor de los objetos clave en cada foto y asignarles una clase:
        *   `fishing_float` (el icono de pesca).
        *   `key_e`, `key_r`, `key_t` (los botones).
        *   `bar_green`, `bar_red` (si hay barras de progreso).
        *   `fish_name` (el texto del resultado).

## Fase 2: Entrenamiento del Modelo (El Cerebro)
Usaremos **YOLOv8 (Nano)**, que es la versión más rápida y ligera, perfecta para correr en tiempo real en tu PC sin necesitar una super gráfica.
1.  **Configuración del Entorno**:
    *   Instalar librería: `pip install ultralytics`.
2.  **Entrenamiento**:
    *   Si tienes buena GPU (NVIDIA), entrenamos en tu PC.
    *   Si no, usamos **Google Colab** (gratis y rápido) para entrenar el modelo en la nube con tus fotos.
    *   El resultado será un archivo `best.pt` (tu modelo entrenado).
3.  **Validación**:
    *   Comprobar que el modelo detecta bien las letras y el icono en imágenes que nunca ha visto.

## Fase 3: Integración en el Bot (El Trasplante)
Reemplazaremos la lógica "rígida" actual por la lógica "flexible" de la IA.
1.  **Nuevo Módulo de Visión (`ai_vision.py`)**:
    *   Cargará el modelo `best.pt`.
    *   Recibirá la captura de pantalla de `mss`.
    *   Devolverá una lista de lo que ve: `[{"clase": "key_e", "confianza": 0.95, "posicion": (x,y)}, ...]`.
2.  **Refactorización de `FishingBot`**:
    *   Eliminar `calibrate_regions.py` (¡ya no hace falta!).
    *   Eliminar `config.json` con coordenadas (solo quedarán configuraciones de tiempos/teclas).
    *   Cambiar la lógica del bucle principal:
        *   *Antes*: "¿El píxel en (100,100) es verde?"
        *   *Ahora*: "¿Hay algún objeto `key_e` en la pantalla con confianza > 80%?"

## Fase 4: Lógica Avanzada y Humanización
Con la IA viendo la pantalla, mejoramos la toma de decisiones.
1.  **Detección de Estado por Contexto**:
    *   Si la IA ve el objeto `fish_name`, sabemos 100% que la pesca terminó (adiós problemas de timeout).
2.  **Centrado Automático**:
    *   Si la ventana del juego se mueve, la IA nos da las nuevas coordenadas (x,y) de los botones al instante. El bot sigue funcionando sin reiniciar.

## Resumen de Pasos Inmediatos (Para empezar ya)
1.  **Paso 1**: Crear el script de recolección de datos (`capture_data.py`).
2.  **Paso 2**: Jugar un rato (o dejar al bot actual jugar) mientras el script guarda fotos.
3.  **Paso 3**: Subir esas fotos a Roboflow y empezar a dibujar cajitas (etiquetar).