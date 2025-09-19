import os
import json
import traceback
import requests
from obs import ObsClient

INPROC_PREFIX = "en_proceso/"
OK_PREFIX     = "procesado_ok/"
ERR_PREFIX    = "procesado_error/"

def handler(event, context):
    print("=== Evento recibido desde OBS ===")
    try:
        print(json.dumps(event, indent=2))
    except Exception:
        print(str(event))

    archivo_actual = None

    # === Variables de entorno ===
    OBS_AK       = os.getenv("OBS_AK")
    OBS_SK       = os.getenv("OBS_SK")
    OBS_ENDPOINT = os.getenv("OBS_ENDPOINT")
    BUCKET_NAME  = os.getenv("BUCKET_DEFAULT", "matibucket")

    DIFY_API_URL = os.getenv("DIFY_API_URL")
    DIFY_API_KEY = os.getenv("DIFY_API_KEY")

    # Validar envs mínimas
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

    # === Cliente OBS ===
    try:
        obs_client = ObsClient(
            access_key_id=OBS_AK,
            secret_access_key=OBS_SK,
            server=OBS_ENDPOINT
        )
    except Exception as e:
        print("Error creando cliente OBS:", str(e))
        return {"statusCode": 500, "body": "Error creando cliente OBS"}

    if "data" in event and "obs" in event["data"]:
        try:
            key = event["data"]["obs"]["object"]["key"]
            print("Archivo detectado:", key)
            archivo_actual = key

            # 1) Ignorar eventos generados por nuestros propios movimientos
            if key.startswith(INPROC_PREFIX) or key.startswith(OK_PREFIX) or key.startswith(ERR_PREFIX):
                print("Evento ignorado (prefijo interno) para evitar loops.")
                return {"statusCode": 200, "body": json.dumps(f"Ignorado: {key}")}

            # 2) Validar que sea un objeto con nombre
            nombre_archivo = key.split("/")[-1].strip()
            if not nombre_archivo:
                print("Key inválida: no hay filename.")
                return {"statusCode": 400, "body": json.dumps("Key inválida (sin filename)")}

            # Paso 1: mover a carpeta en_proceso
            new_key = f"{INPROC_PREFIX}{nombre_archivo}"
            if new_key == key:
                print("Origen y destino son iguales; no se mueve.")
            else:
                print(f"Moviendo archivo a: {new_key}")
                obs_client.copyObject(BUCKET_NAME, key, BUCKET_NAME, new_key)
                obs_client.deleteObject(BUCKET_NAME, key)
                print("Archivo movido correctamente a en_proceso.")

            # Paso 2: generar URL firmada
            signed = obs_client.createSignedUrl(
                method='GET',
                bucketName=BUCKET_NAME,
                objectKey=new_key,
                expires=1800
            )
            signed_url = signed.get('signedUrl') or signed.get('SignedUrl')
            if not signed_url:
                raise RuntimeError("No se pudo obtener signedUrl de OBS")
            print(f"URL firmada generada {signed_url}.")

            # Paso 3: enviar a Dify
            payload = {
                "inputs": {
                    "inputPDF": {
                        "transfer_method": "remote_url",
                        "url": signed_url,
                        "type":"document"
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
                dify_resp = requests.post(DIFY_API_URL, headers=headers, json=payload, timeout=600)
                print("Respuesta Dify:", dify_resp.status_code, dify_resp.text)
            except requests.Timeout:
                err_key = f"{ERR_PREFIX}{nombre_archivo}"
                print(f"Timeout llamando a Dify. Moviendo {new_key} -> {err_key}")
                obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
                obs_client.deleteObject(BUCKET_NAME, new_key)
                return {"statusCode": 504, "body": json.dumps(f"Dify timeout; movido a {err_key}")}

            if not (200 <= dify_resp.status_code < 300):
                err_key = f"{ERR_PREFIX}{nombre_archivo}"
                preview = dify_resp.text[:500] if dify_resp.text else ""
                print(f"Dify devolvió {dify_resp.status_code}. Moviendo {new_key} -> {err_key}. Resp: {preview}")
                obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
                obs_client.deleteObject(BUCKET_NAME, new_key)
                return {"statusCode": dify_resp.status_code, "body": json.dumps(f"Error Dify; movido a {err_key}")}

            # Si todo OK
            ok_key = f"{OK_PREFIX}{nombre_archivo}"
            print(f"Dify OK. Moviendo {new_key} -> {ok_key}")
            obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, ok_key)
            obs_client.deleteObject(BUCKET_NAME, new_key)

            return {
                "statusCode": 200,
                "body": json.dumps(f"Archivo {archivo_actual} procesado OK y movido a {ok_key}")
            }

        except Exception as e:
            print("Error durante el procesamiento:", str(e))
            print(traceback.format_exc())
            try:
                if 'new_key' in locals():
                    err_key = f"{ERR_PREFIX}{nombre_archivo}"
                    print(f"Moviendo {new_key} -> {err_key} por error.")
                    obs_client.copyObject(BUCKET_NAME, new_key, BUCKET_NAME, err_key)
                    obs_client.deleteObject(BUCKET_NAME, new_key)
            except Exception as ee:
                print("Fallo moviendo a carpeta de error:", str(ee))
            return {"statusCode": 500, "body": f"Error: {str(e)}"}

    else:
        print("Estructura de evento inesperada.")

    if archivo_actual:
        return {"statusCode": 200, "body": json.dumps(f"Evento recibido para {archivo_actual}")}
    else:
        return {"statusCode": 400, "body": json.dumps("No se recibió ningún archivo válido")}
