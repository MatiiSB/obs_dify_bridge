# obs_dify_bridge
Pipeline serverless en Huawei Cloud que detecta PDFs en OBS, los mueve a en_proceso/, genera una URL firmada y la envía a Dify para procesarlos. Según el resultado, los organiza automáticamente en procesado_ok/ o procesado_error/.
