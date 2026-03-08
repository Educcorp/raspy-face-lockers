# 🚀 INICIO RÁPIDO - Smart Locker Camera System

## ⚡ En 30 Segundos

```bash
# 1. Ir al directorio del proyecto
cd ~/Documents/GitHub/raspy-face-lockers

# 2. Ejecutar la aplicación
/usr/bin/python3 main.py --mode locker
```

**¡Eso es todo!** ✅

---

## 📋 Pre-requisitos (Verificar)

```bash
# 1. Cámara habilitada en Raspberry Pi
sudo raspi-config
# → Interface Options → Camera → Enable
# → Reboot cuando se pida

# 2. Verificar que funciona
libcamera-hello    # Debe mostrar preview

# 3. OpenCV y dependencias instaladas
pip install -r requirements.txt
```

---

## 🎯 Modos de Ejecución

### Modo Locker (Pantalla Física)
```bash
/usr/bin/python3 main.py --mode locker
```
- Pantalla 800×480 para kiosk
- Reconocimiento facial
- Usuario ve: "Acerca tu rostro"

### Modo Admin (Panel Control)
```bash
/usr/bin/python3 main.py --mode admin
```
- Panel de administración (desarrollo)
- Gestión de usuarios
- Historial de accesos

### Con Script Helper
```bash
chmod +x run.sh
./run.sh --mode locker
./run.sh --mode admin
```

---

## 🔍 Si Algo No Funciona

### 1. **Verificar cámara**
```bash
python3 diagnose_camera.py
```

Debe mostrar:
```
✓ OpenCV Camera................... PASS
✓ Libcamera/Picamera2............ PASS
✓ Face Recognition Module........ PASS
3/5 pruebas pasadas ✅
```

### 2. **Ver logs**
```bash
tail -f logs/locker_system.log
```

### 3. **Modo Debug**
```bash
LOG_LEVEL=DEBUG /usr/bin/python3 main.py --mode locker
```

### 4. **Problemas comunes**

| Problema | Solución |
|----------|----------|
| `libcamera-hello: not found` | `sudo apt install libcamera-apps` |
| `ModuleNotFoundError: picamera2` | Usar `/usr/bin/python3` en lugar de venv |
| `No se puede capturar frames` | Ejecutar `libcamera-hello` y revisar logs |
| `Modelo DNN no encontrado` | Ejecutar `python3 download_models.py` |

---

## 📦 Lo que se Instaló

✅ **Módulo de Reconocimiento Facial**
- Acceso a cámara via picamera2
- Detección mediante OpenCV DNN
- Fallback a OpenCV si falla picamera2

✅ **Configuración**
- `config.py` - Todos los parámetros configurables
- `core/face_recognition.py` - Módulo principal

✅ **Herramientas**
- `diagnose_camera.py` - Verificación del sistema
- `download_models.py` - Descarga de modelos AI
- `SETUP_GUIDE.md` - Guía completa
- `SOLUTION_SUMMARY.md` - Detalles técnicos

---

## 💡 Tips

1. **Pantalla Full-Screen en RPi física**
   Edit `ui/app.py` y descomenta:
   ```python
   self.overrideredirect(True)   # kiosk sin decoración
   ```

2. **Cambiar resolución**
   Edit `config.py`:
   ```python
   CAMERA_CONFIG = {
       "width": 800,   # cambiar
       "height": 600,  # cambiar
   }
   ```

3. **Ajustar sensibilidad de detección**
   Edit `config.py`:
   ```python
   FACE_DETECTION_CONFIG = {
       "confidence_threshold": 0.7,  # más estricto
   }
   ```

---

## 📚 Documentación Completa

- **SETUP_GUIDE.md** - Guía de instalación paso a paso
- **SOLUTION_SUMMARY.md** - Explicación técnica completa
- **diagnose_camera.py** - Script de diagnóstico interactivo
- Comentarios en código - Docstrings en español

---

## 🎬 Siguiente Paso

Ejecuta:
```bash
/usr/bin/python3 main.py --mode locker
```

Y verás:
```
Smart Locker
════════════════════
🔒 Acerca tu rostro a la cámara
● ● ●
[pressiona CTRL+C para salir]
```

---

**¡Listo!** 🎉

¿Preguntas? Ejecuta `python3 diagnose_camera.py`

