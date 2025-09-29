import os
import json
import traceback
import requests
from obs import ObsClient

# Prefijos de carpetas
INPROC_PREFIX = "en_proceso/"
OK_PREFIX     = "procesado_ok/"
ERR_PREFIX    = "procesado_error/"

def handler(event, context):
    print("=== Evento recibido desde OBS ===")
    try:
        print(json.dumps(event, indent=2))
    except Exception:
        print("No se pudo imprimir el evento en formato JSON")

    archivo_actual = None

    # === Variables de entorno obligatorias ===
    OBS_AK       = os.getenv("OBS_AK")
    OBS_SK       = os.getenv("OBS_SK")
    OBS_ENDPOINT = os.getenv("OBS_ENDPOINT")
    BUCKET_NAME  = os.getenv("BUCKET_DEFAULT", "matibucket")

    DIFY_API_URL = os.getenv("DIFY_API_URL")
    DIFY_API_KEY = os.getenv("DIFY_API_KEY")

    required_envs = {
        "OBS_AK": OBS_AK,
        "OBS_SK": OBS_SK,
        "OBS_ENDPOINT": OBS_ENDPOINT,
        "DIFY_API_URL": DIFY_API_URL,
        "DIFY_API_KEY": DIFY_API_KEY,
    }
    missing = [k for k, v in required_envs.items() if not v]
    if missing:
        msg = f"Config incompleta. Faltan: {', '.join(missing)}"
        print(msg)
        return {"statusCode": 500, "body": msg}

    # === Crear cliente OBS ===
    try:
        obs_client = ObsClient(
            access_key_id=OBS_AK,
            secret_access_key=OBS_SK,
            server=OBS_ENDPOINT
        )
    except Exception as e:
        print("Error creando cliente OBS:", str(e))
        return {"statusCode": 500, "body": "Error creando cliente OBS"}

    # === Validar evento ===
    if not ("data" in event and "obs" in event["data"]):
        print("Estructura de evento inesperada.")
        return {"statusCode": 400, "body": json.dumps("Evento no válido")}

    try:
        key = event["data"]["obs"]["object"]["key"]
        archivo_actual = key.replace("+", " ")
        print("Archivo detectado:", archivo_actual)

        # Ignorar archivos ya procesados
        if archivo_actual.startswith((INPROC_PREFIX, OK_PREFIX, ERR_PREFIX)):
            print("Evento ignorado (prefijo interno).")
            return {"statusCode": 200, "body": json.dumps(f"Ignorado: {archivo_actual}")}

        # Extraer nombre del archivo
        nombre_archivo = archivo_actual.split("/")[-1].strip()
        if not nombre_archivo:
            print("Key inválida: no hay filename.")
            return {"statusCode": 400, "body": json.dumps("Key inválida (sin filename)")}

        # === Paso 1: mover archivo a en_proceso ===
        new_key = f"{INPROC_PREFIX}{nombre_archivo}"
        if new_key != archivo_actual:
            try:
                resp = obs_client.copyObject(BUCKET_NAME, archivo_actual, BUCKET_NAME, new_key)
                if resp.status < 300:
                    print(f"Archivo movido a {new_key}")
                else:
                    print(f"Error moviendo archivo: {resp.errorMessage}")
                obs_client.deleteObject(BUCKET_NAME, archivo_actual)
            except Exception as e:
                print("Error moviendo archivo:", str(e))
                return {"statusCode": 500, "body": "Error moviendo archivo a en_proceso"}
        else:
            print("Origen y destino son iguales, no se mueve.")

        # === Paso 2: generar URL firmada ===
        try:
            signed = obs_client.createSignedUrl(
                method='GET',
                bucketName=BUCKET_NAME,
                objectKey=new_key,
                expires=1800
            )
            signed_url = signed.get('signedUrl') or signed.get('SignedUrl')
            if not signed_url:
                raise RuntimeError("No se pudo obtener signedUrl de OBS")
            print(f"URL firmada generada: {signed_url}")
        except Exception as e:
            print("Error generando URL firmada:", str(e))
            return {"statusCode": 500, "body": "Error generando URL firmada"}

        # === Paso 3: enviar a Dify ===
        payload = {
            "inputs": {
                "inputPDF": {
                    "transfer_method": "remote_url",
                    "url": signed_url,
                    "type": "document"
                },
                "objectKey": "new_key"
            },
            "response_mode": "blocking",
            "user": "fg"
        }
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }

        print("Payload a enviar a Dify:", json.dumps(payload, indent=2))

        try:
            dify_resp = requests.post(DIFY_API_URL, headers=headers, json=payload)
            print("Respuesta Dify:", dify_resp.status_code, dify_resp.text)
        except requests.Timeout:
            err_key = f"{ERR_PREFIX}{nombre_archivo}"
            print(f"Timeout con Dify. Moviendo {new_key} -> {err_key}")
            obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
            obs_client.deleteObject(BUCKET_NAME, new_key)
            return {"statusCode": 504, "body": f"Dify timeout; movido a {err_key}"}

        # === Paso 4: procesar respuesta de Dify ===
        if not (200 <= dify_resp.status_code < 300):
            err_key = f"{ERR_PREFIX}{nombre_archivo}"
            preview = dify_resp.text[:300]
            print(f"Dify devolvió {dify_resp.status_code}. Moviendo {new_key} -> {err_key}")
            obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
            obs_client.deleteObject(BUCKET_NAME, new_key)
            return {"statusCode": dify_resp.status_code, "body": f"Error Dify: {preview}"}

        ok_key = f"{OK_PREFIX}{nombre_archivo}"
        print(f"Dify OK. Moviendo {new_key} -> {ok_key}")
        obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, ok_key)
        obs_client.deleteObject(BUCKET_NAME, new_key)

        return {"statusCode": 200, "body": f"Archivo {archivo_actual} procesado OK y movido a {ok_key}"}

    except Exception as e:
        print("Error general durante el procesamiento:", str(e))
        print(traceback.format_exc())
        if 'new_key' in locals():
            try:
                err_key = f"{ERR_PREFIX}{nombre_archivo}"
                obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
                obs_client.deleteObject(BUCKET_NAME, new_key)
                print(f"Movido a carpeta de error: {err_key}")
            except Exception as ee:
                print("Fallo moviendo a carpeta de error:", str(ee))
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
