# obs_dify_bridge
Pipeline serverless en Huawei Cloud que detecta PDFs en OBS, los mueve a en_proceso/, genera una URL firmada y la envía a Dify para procesarlos. Según el resultado, los organiza automáticamente en procesado_ok/ o procesado_error/.

# Integración OBS → FunctionGraph → Dify

Este proyecto implementa un flujo serverless en **Huawei Cloud** que procesa archivos PDF subidos a OBS, los envía a **Dify** para su análisis y los clasifica automáticamente según el resultado.

---

## 🚀 Flujo de trabajo
1. Un archivo PDF es subido a la carpeta `procesar/` en el bucket OBS.
2. **FunctionGraph** se activa mediante un trigger de OBS.
3. El archivo se mueve a la carpeta `en_proceso/`.
4. FunctionGraph genera una **URL firmada** de OBS.
5. Se envía un payload a la API de **Dify** con esa URL.
6. Según la respuesta de Dify:
   - ✅ Éxito → se mueve a `procesado_ok/`
   - ❌ Error → se mueve a `procesado_error/`

---

## ⚙️ Configuración previa
1. **Crear bucket en OBS**  
   - Carpetas requeridas: `procesar/`, `en_proceso/`, `procesado_ok/`, `procesado_error/`

2. **Configurar Dify**  
   - Crear un workflow que reciba `inputPDF` y `objectKey`.
   - Obtener la `API Key` y la `URL` de ejecución (`/v1/workflows/run`).

3. **FunctionGraph**
   - Crear una función en Python 3.9
   - Subir el código de `index.py`
   - Configurar variables de entorno:
     - `OBS_AK` → Access Key
     - `OBS_SK` → Secret Key
     - `OBS_ENDPOINT` → Endpoint de OBS (ej: `https://obs.la-south-2.myhuaweicloud.com`)
     - `BUCKET_DEFAULT` → Nombre del bucket
     - `DIFY_API_URL` → URL del workflow de Dify
     - `DIFY_API_KEY` → API Key de Dify

4. **Crear triggers**
   - **OBS Trigger**: ObjectCreated → carpeta `procesar/`

---

## ▶️ Ejecución
1. Subir un archivo **PDF** a la carpeta `procesar/`.
2. FunctionGraph moverá el archivo a `en_proceso/` y lo enviará a Dify.
3. Verificar resultado en:
   - `procesado_ok/` → si fue exitoso.
   - `procesado_error/` → si hubo error.

---

## 📂 Estructura del bucket
matibucket/
├─ procesar/
├─ en_proceso/
├─ procesado_ok/
└─ procesado_error/

---

Documentacion:
-  Como obtener AK/SK (https://support.huaweicloud.com/intl/en-us/iam_faq/iam_01_0618.html)
-  OBS Trigger (https://support.huaweicloud.com/intl/en-us/usermanual-functiongraph/functiongraph_01_0205.html)
