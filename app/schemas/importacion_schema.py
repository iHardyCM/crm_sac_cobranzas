from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ImportacionConfiguracion(BaseModel):
    id_config: int
    cartera: Optional[str] = None
    producto: Optional[str] = None
    idcartera: Optional[int] = None
    tabla_destino: Optional[str] = None
    tabla_historica: Optional[str] = None
    clave_cruce: Optional[str] = None
    metodo_lectura: Optional[str] = None
    permite_columnas_nuevas: Optional[bool] = None
    requiere_orden_columnas: Optional[bool] = None
    frecuencia: Optional[str] = None
    campo_periodo_actual: Optional[str] = None
    campo_periodo_historico: Optional[str] = None
    tipo_periodo: Optional[str] = None
    formato_periodo: Optional[str] = None
    requiere_transformacion_historico: Optional[bool] = None
    tipo_estructura_historico: Optional[str] = None
    tabla_actual_es_mensual: Optional[bool] = None


class ImportacionAnalisisResponse(BaseModel):
    id_config: int
    cartera: Optional[str] = None
    producto: Optional[str] = None
    tabla_destino: str
    tabla_historica: Optional[str] = None
    periodo: str
    tipo_carga: str
    hojas_disponibles: List[str]
    hoja_usada: str
    total_filas: int
    total_columnas_archivo: int
    columnas_archivo: List[str]
    columnas_destino: List[str]
    columnas_coincidentes: List[Dict[str, Any]]
    columnas_faltantes_en_archivo: List[str]
    columnas_nuevas_en_archivo: List[str]
    columnas_generadas: List[Dict[str, Any]]
    columnas_problema: List[Dict[str, Any]]
    errores_bloqueantes: List[Dict[str, Any]]
    advertencias: List[Dict[str, Any]]
    infos: List[Dict[str, Any]]
    impacto: Dict[str, Any]
    diagnostico_cruce: Dict[str, Any]
    duplicados_archivo: int
    filas_duplicadas_preview: List[Dict[str, Any]]
    columnas_clave_cruce: List[str]
    columnas_clave_encontradas: List[str]
    columnas_clave_faltantes: List[str]
    preview: List[Dict[str, Any]]
    alertas: List[Dict[str, str]]
