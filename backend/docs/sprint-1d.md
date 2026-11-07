# Sprint 1D: recuperación y reconstrucción Markov

## Resultado y punto de parada

Se ha reconstruido el resultado académico MAIN y ROBUST a precisión de máquina,
pero ambas ejecuciones académicas reproducidas terminan sin convergencia del
optimizador. MAIN converge al ampliar a 500 iteraciones sin cambiar etiquetas.
ROBUST converge, pero cambia 35 etiquetas train, exactamente 35 targets de los
5.016 utilizados por el XGBoost ROBUST causal-v1, y 50 etiquetas históricas.

No hay una pareja convergida que conserve la referencia exigida. El estado es
`blocked_stop_for_review`. No se realizan más ajustes ni se inicia operación.

Experimento completo: `backend/experiments/sprint-1d-markov-v2/summary.json`.

## Recuperación histórica

Se inspeccionaron ambos árboles locales y los blobs de notebooks/modelos en
todas las referencias Git alcanzables: 42 blobs de notebooks del TFM, sin
modelos serializados en el historial. La versión actual del notebook 03 usa
`selected_res.params` en memoria, pero no exporta el vector.

Se recuperó una salida antigua MAIN de MS(3), en el blob Git
`a040cd6d3020a861c99bdc3aee0febe5be4b6ce7`, celda 15. Contiene coeficientes
redondeados y resultados estadísticos. No es un vector original de precisión
completa y no se recuperaron coeficientes ROBUST equivalentes.

El vector redondeado MAIN se filtró sin ajuste: error máximo de probabilidad
0,101989 y 98 etiquetas diferentes. No se aceptó como modelo original ni se
utilizó como inicialización para optimizar la reproducción.

La búsqueda y el texto original recuperado quedan en `recovery.json`; el ensayo
sin ajuste queda en `rounded_recovery_filter.json`.

## Configuración y reconstrucción controlada

Se verificaron los datos y sus hashes contra las mismas referencias utilizadas
por causal-v1. Los retornos de `dataset_cap4_input.csv` coinciden exactamente con
los de los CSV de regímenes completos, en las 6.651 fechas. No hay retornos
ausentes, fechas duplicadas ni cambios de orden en los inputs usados.

Markov utiliza toda la muestra train original: 5.274 filas MAIN hasta 31/12/2020
y 5.017 ROBUST hasta 31/12/2019, desde 28/03/2000. No se aplica aquí la purga
de XGBoost: Markov ajusta `ret_1d`, no un objetivo desplazado a la siguiente sesión.

Especificación: `MarkovRegression(ret_1d, k_regimes=3, trend="c",
switching_variance=True)`. Sin estandarizar, sin regresores EWMA/CVaR, sin TVTP.

Se fijaron antes de ajustar dos recetas: BFGS con 100 iteraciones (defaults del
notebook en este runtime) y 500 como diagnóstico de convergencia, ambas con
`em_iter=5`, `search_reps=0`, `disp=False`. Inicialización estacionaria, parámetros
iniciales deterministas. No se usaron búsquedas aleatorias, OOS en el ajuste,
rentabilidad, CVaR de estrategia o backtests para seleccionar candidatos.

Runtime efectivo: Python 3.11.14, statsmodels 0.14.5, NumPy 2.3.4, pandas 2.3.3,
SciPy 1.16.2. La versión statsmodels original no está documentalmente acreditada;
este runtime reproduce su salida con la receta de 100 iteraciones.

Las dos recetas son estados de parada distintos del mismo procedimiento,
no evidencia de dos óptimos locales convergidos. No se ha demostrado optimalidad
global ni estabilidad del estimador mediante multistart.

## Criterios predeclarados

`protocol.json` se escribió antes de los ajustes:

- Convergencia, parámetros finitos, varianzas positivas y transiciones válidas.
- Cero cambios de etiquetas train y de toda la historia.
- Mismos IDs económicos y mapping CVaR train dentro de `atol=1e-12, rtol=1e-10`.
- Primera receta predeclarada que supere todos los criterios técnicos.
- Equivalencia de probabilidades como criterio separado: error máximo <=1e-6.
- La pareja no puede activarse si alguna muestra no supera los criterios.

Un candidato puede ser compatible en etiquetas y mapping sin ser una réplica
numérica de probabilidades; ambas condiciones se registran separadamente.

## Equivalencia obtenida

Comparación sobre 6.651 observaciones hasta 22/05/2026:

| Muestra / receta | Convergencia | Log-likelihood train | Error máx. probabilidades | Cambios train / total | Mapping original | Validación técnica |
| --- | --- | --- | --- | --- | --- | --- |
| MAIN 100 | No | 15669,366940542592 | 2,22e-16 | 0 / 0 | Sí | Rechazada por convergencia |
| MAIN 500 | Sí | 15669,36796559226 | 0,00180944 | 0 / 0 | Sí | Superada, solo candidato offline |
| ROBUST 100 | No | 14999,238018749485 | 1,11e-16 | 0 / 0 | Sí | Rechazada por convergencia |
| ROBUST 500 | Sí | 14999,544490076976 | 0,04697795 | 35 / 50 | No | Rechazada por compatibilidad |

Las likelihoods de las recetas 100 coinciden con las deducidas de los AIC
originales (12 parámetros). BFGS devuelve `warnflag=1` y `ConvergenceWarning`:
se alcanzó el presupuesto sin cumplir convergencia. Máximo absoluto del
gradiente reportado: 0,011802 MAIN y 0,153981 ROBUST. Las recetas 500 terminan
con `warnflag=0` y máximos de gradiente 8,88e-6 y 8,29e-6.

Esto aporta evidencia fuerte de que los CSV académicos corresponden al resultado
del ajuste detenido a 100 iteraciones, no a los ajustes convergidos posteriores.
No se modifica el estado de convergencia para aceptar esos resultados.

## IDs, transiciones y CVaR

Los IDs económicos se conservan en todas las recetas:

| Muestra | Low Risk | Medium Risk | High Risk |
| --- | --- | --- | --- |
| MAIN | 0 | 2 | 1 |
| ROBUST | 0 | 1 | 2 |

Las tablas académicas contienen transiciones **empíricas de argmax**, no la matriz
paramétrica latente. Se comparan por separado. Con 100 iteraciones, ambas matrices
empíricas coinciden exactamente con las reconstruidas desde etiquetas académicas.
MAIN 500 también coincide; ROBUST 500 presenta diferencia máxima 0,00297236.

Las matrices paramétricas quedan persistidas en cada `validation.json`, orientadas
como filas=origen, columnas=destino. statsmodels las representa internamente como
`[destino, origen]`; no se confunden ambas convenciones.

Las medias de CVaR train de las recetas 100 coinciden con las originales hasta
redondeo (~8e-17). MAIN 500 mantiene esas medias. ROBUST 500 cambia las medias por
aproximadamente +0,0000164800 / +0,0001423206 / +0,0000680830 para low/medium/high.

| Mapping | Low | Medium | High |
| --- | --- | --- | --- |
| MAIN académico y 500 | 1 | 0,5905564268560006 | 0,35555173729762624 |
| ROBUST académico y 100 | 1 | 0,6007078845462255 | 0,38855936256726015 |
| ROBUST 500 | 1 | 0,6029670173227544 | 0,3887698806841147 |

El mapping académico asociado se conserva intacto y el calculado para cada
candidato se registra separado. No se sustituye el primero por el segundo.

## Persistencia y compatibilidad con XGBoost

Cada muestra tiene carpetas `notebook_100/` y `convergence_500/` con:

- `parameters.json`: vector de 12 parámetros a precisión completa, nombres y
  parámetros iniciales del modelo. Son reconstruidos, no archivos originales.
- `metadata.json`: configuración, inicialización estacionaria y vector inicial,
  train, versión, IDs económicos, hashes, correspondencia con el metadata exacto
  del XGBoost causal-v1 y estado de validación.
- `cvar_mapping.json`: mapping académico asociado.
- `validation.json`: convergencia, optimizador, avisos, likelihood, transiciones,
  CVaR/mappings y diferencias por muestra.
- `probabilities.csv.gz` y `comparison_by_date.csv.gz`: evidencia del experimento,
  separada de todos los CSV operativos.

Los inputs de train y filtrado también quedan guardados por muestra. Los hashes
de referencias están en `source_provenance.json`. La persistencia es JSON, no
pickle. `regimes/persistence.py` solo filtra con parámetros congelados, comprueba
runtime/hashes e impide cargar candidatos rechazados mediante el cargador normal.

MAIN 500 conserva los 5.273 targets efectivos del XGBoost MAIN causal-v1. ROBUST
500 cambia **35 de los 5.016 targets** del XGBoost ROBUST. No son errores nuevos
de clasificación de XGBoost: son cambios en el objetivo que utilizó para aprender.
Coincidir en IDs no basta para declarar compatibilidad.

MAIN 500 pasa la validación técnica individual, pero no replica exactamente las
probabilidades académicas y no está activado. ROBUST no tiene candidato que
cumpla simultáneamente convergencia y compatibilidad. No se aprueba una pareja.

## Incidente numérico preservado

`sprint-1d-markov-v1` conserva una ejecución fallida: su primer ajuste MAIN 100
terminó, pero un validador con límite exacto [0,1] rechazó el filtro antes de
guardar los parámetros. Se corrigió únicamente el validador y se repitió esa
misma receta en v2, que contiene los cuatro ajustes documentados.

El filtro nativo llega a 1,0000000000000007 y los errores de suma son menores
de 8e-16. Se tolera únicamente redondeo de límites a 1e-12 y suma a 1e-10, sin
clipping ni renormalización. Los valores nativos se conservan. No se cambió el
modelo, la optimización o los criterios de equivalencia para corregirlo.

## Pruebas y límites

Se conservan las 49 pruebas anteriores y se añaden 12 de Markov. En el backend
hay 54 superadas y siete omitidas por runtime. Las cuatro pruebas de artefactos
Markov y las tres nativas XGBoost se ejecutaron y pasaron en `fin-forecasting`;
también pasaron allí las ocho pruebas genéricas Markov. Son 61 pruebas distintas
verificadas entre ambos entornos, sin entrenar dentro de los tests.

Se comprueban recarga exacta de los cuatro vectores, probabilidades históricas,
normalización, orientación de transiciones, etiquetas/mappings, vínculos con
XGBoost, rechazo de parámetros alterados o candidatos no validados y filtrado
de observaciones OOS nuevas. Añadir/modificar retornos futuros no altera el
prefijo filtrado. Las pruebas de causalidad corresponden a OOS: la estimación
de parámetros utiliza todo el periodo train, como en el TFM.

No se acredita optimalidad global, equivalencia entre versiones statsmodels,
ni una solución ROBUST convergida que preserve los targets actuales.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 /home/apalo/miniconda3/envs/fin-forecasting/bin/python -B \
  -m unittest discover -s tests -p 'test_markov*.py' -v
```

El script de reconstrucción exige `--reconstruct`, un directorio nuevo y no
sobrescribe experimentos. No se conecta al pipeline diario. Para revisar este
resultado se leen los JSON existentes; no hay que volver a ajustar modelos.

## Alternativas que requieren decisión antes de continuar

1. **Fidelidad a los resultados originales:** aceptar explícitamente los vectores
   reconstruidos de 100 iteraciones como modelos académicos congelados con la
   limitación de no convergencia. Mantendrían labels, probabilidades, CVaR y ambos
   XGBoost causal-v1. Requiere cambiar de forma documentada el criterio de promoción;
   no se han aprobado con una excepción implícita.
2. **Exigir convergencia:** mantener MAIN 500 y versionar una nueva investigación
   ROBUST basada en 500. Requeriría un mapping distinto y un XGBoost ROBUST nuevo
   entrenado con los targets correspondientes, con autorización específica. Los
   resultados originales permanecerían como referencias académicas separadas.

No se recomienda ocultar estas diferencias mediante renombrado de estados ni
buscar configuraciones por su rentabilidad OOS. Ninguna alternativa se aplica.

Después de esa decisión seguirían pendientes el registro de modelos aprobado,
runtime común, publicación atómica, continuidad de señales, conexión con loaders
y API existentes y actualización completa de las seis pestañas. No se inicia
actualización automática, despliegue ni commits.
