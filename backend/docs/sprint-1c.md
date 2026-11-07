# Sprint 1C: XGBoost reproducible con frontera purgada

## Resultado

Se entrenó una única instancia MAIN y una ROBUST, usando la autorización del
Sprint 1C. No se ajustaron hiperparámetros con OOS, no se entrenó Markov y no se
modificaron artefactos académicos u operativos. No hubo avisos de entrenamiento.

Los modelos nuevos no se presentan como los modelos originales recuperados:
son modelos nuevos del mismo diseño, con la corrección temporal autorizada.

Artefactos: `backend/experiments/sprint-1c-causal-v1/`.

| Muestra | Modelo | Filas train | Última fecha features | Última etiqueta conocida |
| --- | --- | --- | --- | --- |
| MAIN | `main/model.ubj` | 5.273 | 30/12/2020 | 31/12/2020 |
| ROBUST | `robust/model.ubj` | 5.016 | 30/12/2019 | 31/12/2019 |

SHA-256 MAIN: `4368859c76af72ba48dd74158251faf0011e6a81c2162f73e94c21d98343469e`.

SHA-256 ROBUST: `f53d36b69f3cb12f25424bd3d0f6e306e04be8719b0c52d5be0e129c739eb2fa`.

## Puerta de preparación

Antes de cualquier `fit`, ambas muestras deben superar:

1. Verificación del hash del maestro congelado y de su identidad con el archivo
   del commit TFM `8dd66a93c06dc3cbfaac29f086ad2625d32d9756`.
2. Las once features obligatorias, numéricas, finitas, con fechas únicas y
   ordenadas. El maestro incluye 6.631 sesiones, 28/03/2000–23/04/2026.
3. Reconstrucción independiente de los indicadores desde precios/retornos del
   mismo commit, y comprobación de retornos contra precios. Error máximo
   3,98e-13 en asimetría; las demás features quedan por debajo de 1e-16.
   Se conservan los valores almacenados para entrenar; no se reemplazan por el
   recálculo ni por el maestro local sobrescrito de 2002.
4. Identidad de fechas y etiquetas de los regímenes train guardados del TFM con
   los regímenes completos verificados por hash. Correspondencia de `ret_1d`,
   EWMA y CVaR entre fuentes dentro de tolerancia numérica.
5. Verificación mediante AST de los dos constructores XGBoost del notebook 05.
   El código de los notebooks 01 y 02 coincide con el commit histórico.
6. Construcción de objetivos antes de recortar cobertura de features. La fecha
   objetivo es explícita y siempre posterior a la fecha de features.
7. Purga de una fila por muestra: features del 31/12/2020 y 31/12/2019 tenían
   como etiqueta el primer régimen OOS. Las etiquetas restantes terminan en
   31/12 del año correspondiente y ninguna alcanza test.

Los inputs quedan verificados por construcción, fuentes académicas y recálculo.
Esto no acredita igualdad con los pesos del XGBoost original: nunca se recuperó
su artefacto ni su entorno completo. Se registra esa limitación.

## Entorno y configuración efectivos

Se utilizó el entorno existente, sin instalar ni actualizar dependencias:

| Componente | Versión |
| --- | --- |
| Python | 3.11.14 |
| pandas | 2.3.3 |
| NumPy | 2.3.4 |
| scikit-learn | 1.7.2 |
| XGBoost | 3.0.5 |

Ejecutable: `/home/apalo/miniconda3/envs/fin-forecasting/bin/python`.

Parámetros preespecificados idénticos al notebook: `n_estimators=300`,
`max_depth=3`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`,
`objective=multi:softprob`, `eval_metric=mlogloss`, `random_state=42`, `n_jobs=-1`.
No se usó early stopping ni conjunto OOS dentro de `fit`.

Cada modelo guarda también `get_params()` y la configuración efectiva del
booster, que resuelve defaults antes no registrados. Los valores no finitos de
parámetros, por ejemplo `missing=NaN`, se representan como strings en JSON
estricto. Estos registros no pretenden recuperar los defaults de la ejecución
académica original.

Orden de features: `ret_1d`, `ret_20d`, `ret_60d`, `ewma_vol`, `vol_20d`,
`vol_60d`, `downside_vol_20d`, `downside_vol_60d`, `cvar_95_60d`, `drawdown`,
`skew_60d`. Clases del clasificador: `[0, 1, 2]`; High Risk es 1 en MAIN y 2
en ROBUST. La correspondencia económica queda guardada por separado.

## Validación comparable

La cobertura del maestro termina el 23/04/2026. Las features de ese día pueden
evaluarse porque su etiqueta de la sesión siguiente está en los regímenes
académicos disponibles. Se excluyen explícitamente 19 predicciones originales
posteriores a ese día por muestra. No se mezclan features de otra procedencia.

La referencia TFM se recalcula sobre las mismas fechas, por eso sus cifras
pueden diferir de las tablas de mayo mostradas en sprints anteriores.

| Muestra | OOS | Accuracy TFM → nuevo | Balanced accuracy TFM → nuevo | Recall High Risk TFM → nuevo | Clases distintas |
| --- | --- | --- | --- | --- | --- |
| MAIN | 04/01/2021–23/04/2026; 1.357 | 0,912307 → 0,910096 | 0,780241 → 0,787041 | 0,515152 → 0,545455 | 11 |
| ROBUST | 02/01/2020–23/04/2026; 1.614 | 0,884758 → 0,885378 | 0,816101 → 0,812454 | 0,658333 → 0,641667 | 7 |

Matrices de confusión: filas=clase verdadera y columnas=clase predicha,
ambas en orden `[0, 1, 2]`:

```text
MAIN TFM                MAIN nuevo
862   0  58             862   0  58
  1  17  15               1  18  14
 43   2 359              46   3 355

ROBUST TFM              ROBUST nuevo
894  76   0             894  76   0
 51 455  18              48 458  18
  1  40  79               1  42  77
```

Diferencia media absoluta de probabilidades, por régimen 0/1/2:

- MAIN: 0,006728 / 0,000801 / 0,007404; diferencia máxima global 0,076944.
- ROBUST: 0,006547 / 0,008372 / 0,002004; diferencia máxima global 0,145386.

La exposición Hard cambia en 11 y 7 sesiones ejecutadas. La exposición
probabilística cambia en todas las sesiones ejecutadas: diferencia media
absoluta 0,002897 MAIN y 0,002990 ROBUST. El máximo es 0,025890 y 0,058076.
Los cambios de exposición Hard máximos son 0,409444 MAIN y 0,399292 ROBUST.

## Impacto sobre estrategias

Backtest con las convenciones originales: una sesión de desfase, exposición por
retorno logarítmico y mapping CVaR train congelado. Se conserva Buy & Hold y
Regime-based; no cambian entre ambas comparaciones. El backtest ML usa 1.356
filas MAIN y 1.613 ROBUST después del desfase.

Retorno acumulado bruto, CVaR diario 95 % y drawdown máximo (valores en %):

| Muestra / estrategia | Retorno TFM → nuevo | CVaR TFM → nuevo | Max DD TFM → nuevo |
| --- | --- | --- | --- |
| MAIN Hard | 84,3945 → 81,8196 | -1,9126 → -1,9154 | -21,7010 → -22,4705 |
| MAIN probabilística | 77,8916 → 77,5051 | -1,9010 → -1,9022 | -21,6979 → -21,7599 |
| ROBUST Hard | 63,9249 → 65,1047 | -2,0754 → -2,0848 | -23,3482 → -23,3151 |
| ROBUST probabilística | 58,5384 → 58,8597 | -2,0764 → -2,0764 | -25,3529 → -25,2645 |

Retorno acumulado neto con coste 0,001 por variación absoluta de exposición:

| Muestra / estrategia | TFM → nuevo |
| --- | --- |
| MAIN Hard | 78,4308 % → 75,2814 % |
| MAIN probabilística | 71,0511 % → 70,5807 % |
| ROBUST Hard | 56,7125 % → 58,2189 % |
| ROBUST probabilística | 51,6213 % → 52,0083 % |

`validation.json` contiene las métricas sin redondear, incluyendo CVaR/drawdown
netos y turnover. `daily_comparison.csv.gz` registra cada clase, probabilidad y
exposición antes/después por fecha. La primera fila no tiene exposición ejecutada
porque el TFM descarta la primera sesión OOS.

Las diferencias no son igualdad de reproducción histórica: intervienen la purga
autorizada, el runtime actual y los inputs recuperados. No se atribuye todo a la
purga ni se afirma que una versión concreta explique cada cambio. No se entrenó
un control sin purga para atribuir causalmente las diferencias. No se optimizó
ningún parámetro para acercar resultados.

## Persistencia y pruebas

Cada directorio MAIN/ROBUST contiene:

- `model.ubj`: modelo nativo XGBoost.
- `metadata.json`: hash, muestra, clases, features, cutoff informativo, versiones,
  parámetros explícitos, hashes de datos y referencia al informe de validación.
- `parameters.json` y `booster_config.json`: configuración explícita y efectiva.
- `training_input.csv.gz` y `validation_input.csv.gz`: inputs completos del
  experimento, con fechas de features/objetivo y once variables en orden fijo.
- `validation_predictions.csv.gz`, `validation_backtest.csv.gz`,
  `validation_metrics.csv.gz`, `daily_comparison.csv.gz` y `validation.json`.
- Inputs y resultados de una inferencia de prueba sin etiquetas futuras.

En la raíz: `preflight.json`, `versions.json`, `runtime.json`, `summary.json` y
`status.json`. Los inputs CSV se guardan con 17 cifras significativas y hashes
del contenido descomprimido y del archivo; para reconstruir sus valores binarios
usar `pd.read_csv(..., float_precision="round_trip")`.

La recarga de ambos modelos produjo predicciones idénticas bit a bit a las
anteriores a serialización sobre todo OOS. Las pruebas nativas verifican además
una observación posterior a entrenamiento sin targets, integridad de inputs,
purga y rechazo de modelos alterados. No prueban entrenamiento bit a bit repetido
en otras máquinas o versiones.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 /home/apalo/miniconda3/envs/fin-forecasting/bin/python -B \
  -m unittest discover -s tests -p test_trained_models.py -v
```

El backend actual no tiene XGBoost instalado: sus pruebas nativas se omiten allí
y se ejecutan realmente en el entorno registrado, sin instalar nada. El cargador
exige la versión XGBoost de los metadatos y verifica el hash antes de cargar.

Resultado: 46 pruebas superadas en el entorno del backend, con las tres pruebas
nativas omitidas allí; esas tres se ejecutaron y superaron en `fin-forecasting`.
Son 49 pruebas distintas verificadas entre ambos entornos. Los 214 archivos
protegidos del TFM, fixtures previas, datos operativos, API pública, Streamlit,
Docker y requirements conservaron sus hashes. También se comprobaron los hashes
de ambos modelos y del código registrado en `preflight.json`.

Para inspeccionar preparación sin entrenar ni crear artefactos:

```bash
/home/apalo/miniconda3/envs/fin-forecasting/bin/python -B \
  scripts/train_xgboost_experiment.py --preflight-only
```

La ejecución de entrenamiento se hizo una sola vez con `--train --output-dir
experiments/sprint-1c-causal-v1`. Ese directorio ya existe: el script rechaza
sobrescribirlo. El entrenamiento no se conecta a ninguna tarea diaria.

## Pendiente antes de uso diario

1. Elegir y fijar el runtime de inferencia del backend: hoy difiere del entorno
   de entrenamiento y no incluye XGBoost. No se cambian dependencias o Docker aquí.
2. Aprobar promoción de estos modelos; conservar su versión y cutoff, sin
   reentrenamiento diario. Ambos modelos tienen entrenamiento histórico estático.
3. Conectar las once features de nuevas sesiones con `predict_regimes`, con
   controles de datos, antigüedad y validación antes de publicar artefactos.
4. Completar la actualización Markov para Regime-based por separado si se quiere
   actualizar todo el producto; XGBoost utiliza las once variables financieras,
   no probabilidades Markov como features de inferencia.
5. Integrar los resultados mediante loaders/servicio existentes y una extensión
   compatible de API; conservar las seis pestañas y diferenciar `proba_*` de
   probabilidades filtradas Markov.

No se inicia integración operativa, servicio, despliegue ni operaciones
financieras. No hay cambios en TFM, CSV operativos, dashboard, API pública,
Docker o requirements. No se hacen commits.
