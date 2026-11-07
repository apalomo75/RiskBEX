# Sprint 2: motor MAIN offline y primera entrega pública incremental

## Alcance terminado

Se consolida un paquete MAIN autónomo, sin alterar parámetros, y un único
servicio interno de inferencia. No hay descargas, fitting, CSV operativos,
cambios de API/Streamlit, workflows activados ni despliegues.

Decisión explícita de producto: MAIN es el único motor diario futuro. ROBUST
permanece como validación académica, con todos sus archivos intactos. El bloqueo
de la pareja MAIN/ROBUST del Sprint 1D no se oculta ni se modifica: el producto
adopta ahora una selección MAIN independiente, autorizada por el usuario.

`main-v1` es la versión del paquete cuantitativo, no un anuncio de RISKBEX v1.0.
La primera entrega pública prevista es RISKBEX v0.1 — Market Risk Monitor.

## Archivos y reutilización

| Componente | Cambio mínimo |
| --- | --- |
| `features/market.py` | Ensambla los indicadores con las funciones existentes de returns, volatility, downside, drawdown y tail_risk. |
| `engine/package.py` | Valida manifiesto, archivos asociados, hashes, runtime, IDs y mapping; carga mediante los loaders de modelos existentes. |
| `engine/service.py` | Precios hasta t -> estado Markov, predicción XGBoost y tres exposiciones siguientes. |
| `scripts/build_main_package.py` | Copia byte a byte los artefactos MAIN seleccionados a un directorio nuevo. |
| `scripts/run_main_offline.py` | CLI reproducible, lee CSV local y emite JSON en stdout; no escribe resultados operativos. |
| `scripts/check_main_engine.py` | Verifica compatibilidad histórica y genera ejemplos reales en memoria. |
| `model_packages/main-v1/` | Manifiesto, checksum y siete archivos MAIN originales copiados sin cambios. |
| `tests/test_main_engine.py` | Integridad, causalidad, estabilidad de ejecución e inferencia real sin fit. |
| `tests/fixtures/sprint2/` | Precios históricos/locales y predicciones causal-v1 con hashes; no son datos descargados. |
| `reports/sprint2/` | Informes y ejemplos de este sprint; separados de todos los CSV operativos. |

Las rutas públicas y sus esquemas, `dashboard.py`, las seis pestañas, Docker,
requirements y workflows no se modifican. El motor no importa el script diario,
que actualmente tiene descarga/escritura en el cuerpo del módulo.

## Paquete y correspondencia de regímenes

`model_packages/main-v1/manifest.json` asocia:

- Markov MAIN convergente, receta BFGS de 500 iteraciones del Sprint 1D.
- XGBoost MAIN causal-v1 del Sprint 1C, sin reentrenar ni modificar.
- Mapping CVaR MAIN original, calculado exclusivamente con train.
- Once features en su orden original, periodos, versiones, inicialización y hashes.
- Evidencia de cero cambios de etiquetas train/históricas MAIN y mapping coincidente.
- Diferencia declarada respecto a probabilidades Markov académicas de 100 iteraciones.

IDs: 0=low_risk, 2=medium_risk, 1=high_risk. Las clases del clasificador son
`[0, 1, 2]`; la interpretación económica no cambia su orden de columnas.

Markov utiliza 5.274 sesiones del 28/03/2000 al 31/12/2020. XGBoost utiliza
5.273 filas, últimas features del 30/12/2020 y última etiqueta del 31/12/2020.
Las señales operativas se permiten estrictamente después del cutoff informativo.

Se validan los hashes de manifiesto y componentes, referencias anidadas, clases,
muestra, orden de features, configuración de indicadores, mapping y versiones.
El paquete puede copiarse a otro directorio y cargar sin acceder a los modelos
originales ni al repositorio académico. No contiene ROBUST.

Runtime requerido, sin instalarlo en este sprint: Python 3.11.14, pandas 2.3.3,
NumPy 2.3.4, SciPy 1.16.2, statsmodels 0.14.5, scikit-learn 1.7.2, XGBoost 3.0.5.
El entorno del backend actual es distinto: no se altera ni se usa como fallback.

## Contrato de precios e inicialización

Entrada: DataFrame o CSV con `date` e `ibex_close`. Las fechas deben estar
ordenadas, ser diarias sin zona horaria ni duplicados, y los precios positivos,
numéricos y finitos hasta el corte. Se presupone que son sesiones cerradas;
el motor offline no acredita cierre real ni frescura de mercado.

Se requiere historia completa desde el ancla 03/01/2000 o desde la primera
sesión de retorno, 04/01/2000. Si empieza el 04/01, se añade explícitamente el
contexto previo persistido: cierre 11.609,98828125 del 03/01. Este cierre se
recuperó de `first_close / exp(first_stored_log_return)`, con el raw del commit
académico y la fecha acreditada por outputs del notebook 01. No se utiliza el
retorno ni ninguna etiqueta que pueda acompañar al CSV de entrada.

El precio ancla sirve solo para calcular el primer retorno. Se excluye antes de
EWMA y drawdown, como en los notebooks 01/02. El calentamiento inicial termina
en 28/03/2000; después se rechazan features ausentes en vez de descartar sesiones.
El hash canónico de los 5.334 precios de contexto/train detecta revisiones o
sesiones históricas perdidas. No se corrigen datos silenciosamente.

`as_of` recorta antes de calcular indicadores. El hash de datos de la señal
corresponde solo al prefijo consumido, nunca a precios futuros ignorados.

## Flujo y significado temporal

1. Verificar paquete, modelos y mapping.
2. Validar y recortar precios a `as_of`; comprobar contexto histórico.
3. Recalcular indicadores causales mediante historia completa, sin ventanas centradas.
4. Filtrar Markov con parámetros congelados desde su fecha inicial original.
5. Aplicar XGBoost únicamente a las once features de la última sesión válida.
6. Aplicar el mismo mapping train a los tres objetivos de exposición.
7. Devolver señal, horizonte, clases, versiones, hashes de modelos/datos y del
   código de inferencia utilizado. No hay hora de ejecución variable en la señal.

Al cierre de t:

`Regime-based_target(t) = exposure(filtered_regime_t)`

`ML_Hard_target(t) = exposure(predicted_regime_t_plus_1)`

`ML_Probability_target(t) = sum(P_ML_t(k) * exposure(k))`

Los tres objetivos se aplicarían durante la siguiente sesión. La señal NO lleva
otro `shift(1)`. Para calcular retorno realizado de t, un consumidor posterior
utilizará el objetivo emitido en t-1 una única vez. La primera actualización de
un lote deberá conservar la señal previa, sin descartar cada día su primera fila.

Markov informa del estado actual y XGBoost del siguiente: sus probabilidades no
son intercambiables. No se necesita `regime_t_plus_1`. El motor devuelve
`target_session_date=null` y horizonte `next_market_session`, evitando inventar
la fecha siguiente con días naturales o ignorar festivos sin calendario de mercado.

## Ejecución offline reproducible

Desde `backend`, con el runtime registrado:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/apalo/miniconda3/envs/fin-forecasting/bin/python -B \
  scripts/run_main_offline.py \
  --package model_packages/main-v1 \
  --prices tests/fixtures/sprint2/extended_prices.csv.gz \
  --as-of 2026-05-15
```

Este comando no requiere Yahoo ni datos operativos. Para otra instalación se
usará un Python con las versiones del manifiesto, sin cambiar la selección de
modelos. La construcción del paquete ya se realizó; el builder rechaza sobrescribirlo.

Ejemplo obtenido realmente al 15/05/2026:

| Campo | Valor |
| --- | --- |
| Cierre IBEX | 17.622,69921875 |
| Retorno logarítmico diario | -0,010527334442857422 |
| Estado Markov | 2, medium_risk |
| Markov: P(low / medium / high) | 0,10314907 / 0,88309066 / 0,01376027 |
| XGBoost: régimen siguiente | 2, medium_risk |
| XGBoost: P(low / medium / high) | 0,18925190 / 0,80897534 / 0,00177276 |
| Objetivo Regime-based | 0,5905564268560006 |
| Objetivo ML Hard | 0,5905564268560006 |
| Objetivo ML Probability-weighted | 0,6676277918505804 |

El resultado completo está en `reports/sprint2/signal-2026-05-15.json`. También
se conservan ejemplos al 04/01/2021 y 23/04/2026. Son datos históricos locales,
no cotizaciones actuales ni una actualización pública activada.

## Compatibilidad y pruebas

La comparación de 6.631 filas de features con el maestro recuperado presenta
error máximo 4,13e-13 (asimetría); el resto queda por debajo de 1,9e-15.

Sobre 1.356 sesiones OOS comunes con el backtest académico MAIN hasta 23/04/2026:
cero cambios del régimen Markov dominante y diferencia máxima de probabilidad
0,000926775. No contradice el máximo 0,00180944 del Sprint 1D, calculado sobre
toda la historia de 6.651 sesiones, incluido entrenamiento.

Las 1.357 predicciones XGBoost coinciden exactamente con las probabilidades y
clases guardadas de causal-v1. Frente al XGBoost académico original se mantienen
las 11 diferencias ya documentadas en Sprint 1C. No se selecciona por rentabilidad.

Las pruebas cubren integridad, clases, normalización, repetición idéntica, ausencia
de futuro incluso en trazabilidad, inferencia sin targets y en fechas posteriores
al 23/04/2026, tres estrategias, paquete autónomo, cambios de historia train y
rechazo de entradas inválidas. `fit` de Markov y XGBoost se parchean para fallar
durante inferencia: el servicio pasa igualmente.

Resultado: 79 pruebas distintas verificadas entre ambos entornos. El backend
ejecutó 61 y omitió 18 por runtime; las once pruebas nativas del motor, cuatro
de Markov y tres de XGBoost se ejecutaron y pasaron en el entorno registrado.
La suite específica de Sprint 2 contiene 18 pruebas (siete de integridad y once
nativas). Se verificaron por hash 290 archivos protegidos sin cambios, incluidos
todos los artefactos ROBUST. `git diff --check` no detectó errores.

```bash
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 /home/apalo/miniconda3/envs/fin-forecasting/bin/python -B \
  -m unittest discover -s tests -p test_main_engine.py -v
```

## Plan mínimo posterior: RISKBEX v0.1 — Market Risk Monitor

No se implementa el simulador ni cartera en este sprint. La publicación requiere
los siguientes bloques acotados y su validación previa:

| Bloque | Cambio mínimo sobre lo existente | Aceptación antes de activar |
| --- | --- | --- |
| Runtime MAIN | Fijar versiones compatibles del backend y empaquetar MAIN de solo lectura con Docker actual. | Carga nativa, tests del motor y regresión API/Streamlit en el runtime final. |
| Pipeline diario MAIN | Separar descarga/escritura de `run_daily_update.py`, reutilizar features/motor y conectar backtests/cola existentes. | Una descarga autorizada controlada; sesiones cerradas, calendario, prefijo histórico verificado y cero fit. |
| Persistencia de resultados | Staging, bloqueo de concurrencia y publicación atómica de una versión completa. | Una ejecución fallida conserva la anterior; repetir inputs no altera resultados. No se escriben artefactos ROBUST. |
| FastAPI | Reutilizar rutas actuales y loaders; exponer señales MAIN y selector de estrategia de forma aditiva, conservando respuesta por defecto. | Contratos previos probados; `p_regime_*` sigue siendo Markov; campos ML diferenciados y run/model IDs visibles. |
| Streamlit actual | Añadir solo selectores/panel de señal dentro de las seis pestañas, fecha efectiva, versión y estado de actualización. | Se ve Markov actual, probabilidades ML siguientes, objetivo CVaR y explicación de la transformación; históricos comparados con Buy & Hold. ROBUST se identifica como referencia histórica. |
| Automatización y publicación | Un job MAIN en el entorno que persiste los resultados; proteger `/run-update` y conectar entrega de artefactos. | Job validado, fallos visibles, HTTPS y salud/readiness. El workflow actual no basta: sus CSV quedan en el runner efímero. |
| Release v0.1 | README público, licencia, metodología/limitaciones, tests reproducibles y changelog. | Clon limpio y demo verificables, URL pública revisada antes de enlazar desde LinkedIn/CV. |

La actualización no cambiará el mapping con OOS ni entrenará modelos a diario.
Los backtests del candidato MAIN se conservarán separados de las referencias
TFM. Un manifiesto de resultados permitirá detectar versiones mezcladas entre
las distintas llamadas del dashboard y mostrar datos atrasados como tales.

Para reducir complejidad, la primera automatización puede ejecutar el comando
validado en el mismo host/volumen de datos del despliegue. Si se usa GitHub
Actions, deberá entregar la versión de datos al entorno servido: no basta con
ejecutar el cálculo en un runner temporal. La elección se cerrará con el destino
de despliegue, sin crear otro frontend ni otra arquitectura de API.

## Riesgos pendientes y versiones posteriores

- El backend actual no es el runtime registrado; no se han instalado dependencias.
- Precios revisados/faltantes pueden activar el rechazo de prefijo histórico.
  Requieren revisión de datos, no alterar modelos para mejorar métricas.
- No se verifica frescura, cierre de vela o calendario real sin el futuro pipeline.
- El modelo es estático con entrenamiento hasta 2020; no se promete ausencia de
  drift ni mejoras universales de rentabilidad/riesgo.
- No hay todavía publicación atómica, job operativo o señales consumidas por UI.
- MAIN 500 conserva labels y mapping, pero no todas las probabilidades académicas.

Roadmap público: v0.1 monitor; v0.2 simulador de capital/estrategias; v0.3 cartera
ficticia con decisiones persistidas; v0.4 explicabilidad/diagnósticos/robustez;
v1.0 integración y estabilidad profesional. Cada entrega tendrá tests,
documentación y changelog. Ninguna versión futura amplía el alcance de Sprint 2.
