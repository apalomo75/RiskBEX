# Sprint 3 — pipeline MAIN versionado

El pipeline reutiliza `engine/service.py`, los once indicadores, el filtrado Markov congelado, XGBoost causal-v1 y los backtests/costes existentes. No entrena, no escribe los CSV heredados y no conecta todavía las rutas públicas ni Streamlit.

## Entrada y flujo

`run_daily_update.py` es el punto de entrada; `run_full_pipeline.py` delega en él. Ambos requieren argumentos explícitos y no tienen efectos al importarse. Las herramientas anteriores se conservan como `run_legacy_market_update.py` y `run_legacy_analytical_pipeline.py`, exclusivamente para ejecución manual. No forman parte de la actualización MAIN: escribirían los CSV heredados y no deben utilizarse para activar este sprint.

1. Adquirir bloqueo `flock` no bloqueante. Validar recibo de regresión, hashes/versiones MAIN e histórico de entrenamiento antes de contactar al proveedor.
2. Leer la última versión validada, o el seed local completo en la primera ejecución. El seed nunca se sobrescribe. El hash de entrenamiento del paquete sigue siendo obligatorio.
3. Calcular la última sesión elegible mediante calendario explícito BME, zona Europe/Madrid y umbral conservador de disponibilidad a las 20:00 locales. Este umbral es una política operativa, no la hora de cierre ni una garantía de entrega. Hasta entonces se utiliza la sesión elegible anterior. Las sesiones reducidas conservan el mismo margen conservador.
4. Solicitar una ventana solapada de diez días naturales y todas las sesiones pendientes a Yahoo `^IBEX`, diario, `auto_adjust=True`, igual que la fuente anterior. La respuesta debe cubrir todas las sesiones solicitadas; datos vacíos, faltantes, desordenados, duplicados, no finitos, no positivos, fuera de ventana o revisados impiden publicar. Las revisiones se rechazan incluso si son pequeñas: requieren revisión humana, no rebase silencioso.
5. Añadir exclusivamente cierres nuevos. Recalcular indicadores desde el ancla original, filtrar con parámetros fijos e inferir XGBoost. Se reconstruye el histórico OOS sin etiquetas futuras.
6. Construir las tres estrategias y Buy & Hold, costes de 0,001 por cambio absoluto de exposición, turnover y métricas brutas/netas. Se conserva la convención académica: retornos logarítmicos, primera fila OOS excluida del realizado y coste inicial cero; no se incorpora un supuesto de compra inicial nuevo.
7. Contrastar señal final individual con histórico de señales; escribir staging, validar fechas/modelos/inventario/hashes y publicar mediante sustitución atómica del puntero.

El calendario incorporado cubre **solo 2026** y falla fuera de cobertura, incluyendo cuando no puede identificar la siguiente sesión. Debe renovarse con un calendario revisado antes del cambio de año. Fuente: [BME, instrucción 65/2025](https://www.bolsasymercados.es/dam/descargas/regulacion/renta-variable/sociedad-de-bolsas/instrucciones-operativas/2025/2025-65-oi-trading-sessions-calendar-2026-eng.pdf). No se infieren festivos históricos mediante una regla de lunes a viernes. El seed anterior al intervalo de actualización debe ser un histórico completo previamente validado; el hash congelado comprueba íntegramente el tramo de entrenamiento, no certifica calendarios de todos los años OOS del seed.

## Temporalidad y frescura

`last_valid_session` / `signal_information_date` describen el cierre utilizado; `generated_at` es el instante de ejecución; `target_session_date` es la siguiente sesión bursátil. Markov describe el estado filtrado actual y XGBoost predice el régimen siguiente. Las exposiciones objetivo emitidas al cierre t se aplican al retorno de t+1. El backtest hace exactamente un shift al alinearlas con retornos; ningún consumidor debe añadir otro shift a la señal emitida.

Una respuesta incompleta no se publica como actual. `pipeline/loaders.py` resuelve una única versión para leer todos sus archivos y recalcula la frescura en cada lectura; una versión que fue actual al publicarse puede estar atrasada hoy. Devuelve también el estado del último intento fallido. Fuera de cobertura de calendario falla explícitamente en vez de afirmar frescura. Los consumidores deberán usar este loader, no confiar indefinidamente en `current_at_generation` del JSON persistido.

## Almacenamiento

El directorio de salida debe estar separado del TFM, modelos, experimentos, fixtures y CSV heredados. Recomendado: `backend/runtime/main/`, ignorado por Git.

- `versions/<sha256>/`: `prices.csv`, `features.csv`, `signals.csv`, `backtest.csv`, `metrics.csv`, `turnover.csv`, `latest.json` y `manifest.json`.
- `current.json`: versión y hash del manifiesto, sustituido mediante `os.replace` tras validar y sincronizar archivos/directorios.
- `status.json` y `attempts/<id>.json`: resultado del último intento e historial de intentos terminados, incluidos errores.
- `update.lock`: exclusión de procesos en el mismo filesystem local Linux.

El identificador depende de precios, paquete, implementación y calendario. Repetir la descarga sin cambios no crea otra versión ni cambia la señal publicada. Una caída antes de promover deja la versión anterior; una versión huérfana íntegra puede reutilizarse al reintentar. Un fallo de disco puede impedir registrar el error; el puntero sigue siendo la autoridad de publicación. Un cierre abrupto del proceso puede dejar un staging huérfano; no se consulta como resultado válido. La corrupción de archivos ya publicados se detecta y se rechaza, sin rollback silencioso. No se afirma exclusión distribuida en NFS ni garantías de object storage.

## Ejecución y validación

Usar el entorno nativo registrado en el paquete (Python 3.11.14, pandas 2.3.3, numpy 2.3.4, scikit-learn 1.7.2, XGBoost 3.0.5, statsmodels 0.14.5). El backend actual de Python 3.13 no contiene XGBoost ni coincide con estas versiones: no es un runtime de inferencia aprobado.

Desde `backend/`, con ese Python:

```bash
python scripts/check_daily_regression.py --output reports/sprint3/regression.json
python -m unittest discover -s tests -p test_daily_pipeline.py -v
python scripts/run_daily_update.py --seed /ruta/precios_validados.csv --store runtime/main --regression-receipt reports/sprint3/regression.json --provider-file /ruta/respuesta_local.csv --now 2026-04-23T20:00:00Z
```

La descarga real requiere sustituir `--provider-file ... --now ...` por `--fetch`; no acepta un reloj simulado. No ejecutar esa opción automáticamente sin las validaciones y autorización correspondientes. No se instala ninguna dependencia nueva. Las pruebas de fallo usan proveedores simulados y directorios temporales.

El recibo vincula la regresión pasada al hash MAIN y a los archivos de implementación. Cualquier cambio cuantitativo/pipeline invalida el recibo y obliga a repetirla. Es una barrera local de integridad, no una firma ni un mecanismo de autorización frente a un operador malicioso con acceso de escritura.

## Regresión cuantitativa

`reports/sprint3/regression.json` contiene 6.631 filas de indicadores, 1.357 predicciones y 1.356 retornos realizados, del 2021-01-05 al 2026-04-23, con fechas idénticas para estrategias comparadas. Reproduce además las referencias académicas originales MAIN y ROBUST sin alterarlas.

- Indicadores: comparación contra master académico recuperado, tolerancia absoluta 1e-12 y relativa 1e-10.
- Predicciones causal-v1: clases y probabilidades coinciden; exposiciones, costes, turnover y métricas coinciden salvo redondeo numérico (máximo observado ~1,3e-14 en columnas diarias).
- Markov500 vs académico100: mismos regímenes, probabilidades difieren hasta 0,0009267752 en las fechas OOS comparadas; exposición Regime-based idéntica. Es la reconstrucción convergente aprobada, no una selección por rentabilidad.
- XGBoost causal-v1 vs académico: 11 clasificaciones distintas por la purga aprobada de la frontera train/OOS; se registran métricas por fechas comunes. ML Hard bruto: retorno acumulado 81,8196% frente a 84,3945%, CVaR diario -1,91536% frente a -1,91262%, drawdown -22,4705% frente a -21,7010%. ML probabilística: retorno 77,5051% frente a 77,8916%, CVaR -1,90224% frente a -1,90098%, drawdown -21,7599% frente a -21,6979%.
- Se detectó y resolvió una diferencia de aritmética: probabilidades nativas float32 se convierten explícitamente a float64 antes de calcular exposiciones, igual que las referencias CSV y la señal individual. No se alteran probabilidades ni modelos.

Los informes de pruebas separados reflejan los dos entornos. Las omisiones por runtime no se cuentan como pruebas superadas. No se compara un periodo truncado con métricas precalculadas de otro periodo: las métricas comparativas se recalculan en fechas comunes.

## Compatibilidad y mínimo restante para v0.1

El adaptador interno entrega latest, manifest, update_status, history, backtest y metrics. Mantiene distinguidas las probabilidades Markov y XGBoost. La procedencia identifica `source_mode=offline_simulation` en ejemplos locales y no afirma haber verificado datos live. No se modifican contratos HTTP ni las seis pestañas. Las rutas actuales siguen leyendo los resultados heredados hasta la siguiente fase; este sprint no hace visible el nuevo motor automáticamente. La ruta existente `/run-update` invoca el script sin los nuevos argumentos: esa invocación termina con error de configuración y no descarga ni escribe datos. Debe conectarse explícitamente al nuevo entrypoint y al runtime aprobado en la siguiente fase; no se considera una actualización API operativa validada. Esta barrera evita ejecutar accidentalmente el pipeline nuevo desde el botón o workflow heredado.

1. Homogeneizar el runtime de inferencia con el paquete aprobado y empaquetar modelos/calendario/almacenamiento persistente en el despliegue existente, sin cambiar frameworks.
2. Conectar loaders internos a rutas existentes mediante adaptadores compatibles y probar respuestas; mostrar fecha efectiva, horizonte, modelo, frescura y fallo de actualización en las visualizaciones existentes.
3. Completar la verificación del proveedor real: cierres, posibles revisiones, continuidad, disponibilidad y condiciones de uso público. Nunca sustituir el snapshot congelado ante revisiones.
4. Validar end-to-end API/dashboard con una publicación completa y con proveedor caído. Documentar que son señales de investigación, no operaciones financieras.
5. Solo entonces autorizar/activar un único programador con el entrypoint explícito, persistencia, logs y alertas; revisar el workflow heredado (sin argumentos, runtime incompatible y horario anterior al margen conservador). No se ha activado ni modificado en este sprint.
6. Preparar README público, changelog v0.1, configuración de despliegue y comprobaciones de publicación. Simulador y cartera ficticia quedan para versiones posteriores.

## Resultado ejecutado

- 103 pruebas distintas superadas entre los dos entornos, cero fallos finales y ninguna prueba omitida en ambos. Backend: 103 descubiertas, 73 superadas y 30 omitidas por runtime. Nativo: 25 pruebas previas y 24 de pipeline superadas; se descuentan duplicados al informar el total. Véase `reports/sprint3/test-summary.json`. Los logs de desarrollo anteriores incluyen fallos corregidos; los archivos indicados en test-summary son la evidencia final.
- Ejemplo offline publicado: seed hasta 2026-04-22, una nueva sesión histórica validada el 2026-04-23, siguiente sesión 2026-04-24. Estado medium_risk; exposición Regime-based/ML Hard 0,5905564268560006 y ML probabilística 0,6352243859971466. Es una simulación con precios históricos reales congelados, no una descarga reciente.
- Se realizó una única invocación controlada de descarga real tras superar las pruebas offline. Falló la resolución DNS de `guce.yahoo.com`. No se obtuvieron cierres nuevos ni se creó una publicación live. El estado fallido y el error constan en `live-update.json` y `live-download.log`. No se reintentó ni se cambió de fuente.
- 323 archivos protegidos comprobados por SHA-256, sin cambios: TFM, modelos, snapshots y código cuantitativo anterior protegido. Véase `preservation.json`.

## Archivos de este sprint

Nuevos: `src/riskbex/pipeline/{__init__,calendar,provider,history,store,service,loaders}.py`, `config/bme-2026.json`, `scripts/check_daily_regression.py`, `scripts/run_legacy_market_update.py`, `scripts/run_legacy_analytical_pipeline.py`, `tests/test_daily_pipeline.py`, esta documentación e informes `reports/sprint3/`. Modificados: `scripts/run_daily_update.py`, `scripts/run_full_pipeline.py`, `.gitignore`, README backend y CHANGELOG. Los cambios pendientes de los sprints anteriores se conservan y no pertenecen a este inventario.
