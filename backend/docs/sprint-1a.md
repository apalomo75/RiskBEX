# Sprint 1A: interpretación train y mapping CVaR

## Alcance y reutilización

Este bloque integra la interpretación económica y exposición del notebook 03
del TFM en el motor existente. No reconstruye la aplicación.

| Componente existente | Cambio mínimo |
| --- | --- |
| `src/riskbex/regimes/interpretation.py` | Resumen independiente de entrenamiento MAIN/ROBUST y orden por EWMA ascendente, luego CVaR firmado ascendente, como el TFM. |
| `src/riskbex/backtesting/exposures.py` | Función CVaR reutilizable; se conservan asignación por régimen y desfase operativo. |
| `scripts/prepare_regime_datasets.py` | Recalcula el resumen train desde regímenes existentes y construye ambos mappings; elimina expectativas fijas 100/75/25. |
| Loaders, esquemas y rutas | Se reutilizan sin modificaciones; se verifican con los nuevos resultados. |
| `dashboard.py` | Se conserva íntegro, incluidas sus seis pestañas, gráficos y funcionalidades. |
| Docker y actualización diaria | Se conservan; su conexión integral pertenece a los siguientes bloques. |

## Contrato implementado

Para cada muestra, el resumen utiliza exclusivamente su columna de partición
`sample_split_main` o `sample_split_robust` con etiqueta `train`. Deben existir
los tres regímenes y valores financieros finitos en entrenamiento. Los datos
OOS no intervienen en etiquetas económicas ni exposición.

`target_exposure = clip((abs(mean_cvar_low_train) / abs(mean_cvar_regime_train)) ** alpha, 0, 1)`

El parámetro principal es `alpha=1`. Se usa la media del indicador móvil CVaR
en cada régimen train, no un cuantil recalculado agrupando retornos por régimen.
Se rechazan severidades nulas/no finitas y exposiciones sin el orden estricto
high < medium < low, como en la validación del TFM. No se fijan IDs económicos
por número: el orden proviene del entrenamiento.

Los mappings conservan las cuatro columnas requeridas por los loaders y añaden
los diagnósticos originales del TFM: medias CVaR, severidad, referencia low,
alpha y metodología. La preparación guarda el mismo resumen train utilizado
para el mapping, de modo que la API no consulte otro resumen de muestra completa.

Compatibilidad: `frequency_pct` sigue siendo una fracción [0, 1], porque el
dashboard existente la formatea como porcentaje. El TFM la exporta multiplicada
por 100; los tests comparan las estadísticas con unidades explícitas.
`risk_severity` conserva su cálculo como campo informativo del esquema actual,
pero deja de determinar el orden económico. Las etiquetas del resumen conservan
su formato existente; las del mapping se normalizan como en el TFM.

## Verificación offline

Desde `backend`, con las dependencias ya disponibles:

```bash
python -B -m unittest discover -s tests -v
```

En este workspace se utiliza `venv/bin/python`. No se añaden dependencias para
las pruebas: se emplea `unittest` y las bibliotecas actuales del backend.

La suite incluye equivalencia MAIN/ROBUST con tablas TFM sin redondear,
invariancia ante cambios OOS, particiones independientes, permutación de IDs,
desempate por CVaR, validaciones de entradas, preparación en directorio temporal,
lectura mediante loaders actuales y backtest existente. Comprueba los 17 paths
y métodos de la API, el handler de resumen y sus esquemas Pydantic; no equivale
a probar transporte HTTP, servicios, Docker o comportamiento visual.

La prueba local adicional verifica los hashes de los regímenes del TFM y
reconstruye sus estadísticas train. Su omisión fuera del workspace se comunica
explícitamente. No se entrenan modelos ni se descargan precios.

## Activación y límites

No se regeneran los CSV operativos en este bloque. Las pantallas seguirán
mostrando los artefactos anteriores hasta ejecutar el pipeline en una fase
posterior. La próxima ejecución de `run_full_pipeline.py` usará la nueva
preparación y cambiará exposiciones, backtest y cola. No anunciar resultados
CVaR nuevos hasta verificar esa generación completa.

Si un ajuste futuro cambia los IDs/etiquetas, también deberán regenerarse los
artefactos dependientes de interpretación (transiciones y duraciones). El runner
actual aún no orquesta todos esos pasos ni publica CSV atómicamente.

Pendientes: recuperación del maestro histórico, frontera del objetivo ML,
convenciones de rentabilidad/drawdown/costes, fechas comunes netas, extracción
XGBoost, estrategias ML y pipeline diario integral. Este bloque no decide
ninguna corrección metodológica pendiente ni declara equivalencia completa del
TFM. No cambia endpoints, frontend, dependencias ni Docker; no incluye commits.
