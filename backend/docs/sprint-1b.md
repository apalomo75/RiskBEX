# Sprint 1B: ML original integrado en el motor existente

## Recuperación: qué existe y qué no

Se revisaron los árboles de ambos repositorios sin recorrer dependencias, los
nombres históricos de archivos en todas las referencias Git locales, código y
outputs de notebooks, y metadatos de los entornos candidatos. No se encontraron
modelos XGBoost serializados ni llamadas de persistencia de modelos en los
notebooks/scripts examinados. No se entrenó ningún modelo.

| Elemento | Resultado |
| --- | --- |
| Modelos MAIN/ROBUST entrenados | No recuperados en el alcance inspeccionado. |
| Predicciones y probabilidades | Recuperadas de `dataset_cap5_regime_predictions.csv` y `_robust`, congeladas con hashes. |
| Configuración | Mismos parámetros explícitos XGBoost MAIN/ROBUST, extraídos del notebook 05. |
| Orden de features | Once variables, incluyendo el join de ocho adicionales desde el maestro. |
| Maestro histórico con once features | Recuperado de Git hasta 23/04/2026, 6.631 filas; cubre todo train, pero es candidato anterior a la ejecución final de mayo. |
| Maestro exacto de mayo | No recuperado completo; el actual arranca en 2002 y no sirve como sustituto. |
| Modelos comparadores | Configuración en notebook 05: logística con scaler train y RF; no se entrenan ni sustituyen XGBoost. |
| Métricas originales | Predicción, backtests, costes, turnover y comparación conjunta conservados en fixtures. |
| Parámetros efectivos/defaults del modelo original | No recuperados: sin modelo serializado ni `get_params`/`save_config` de aquella ejecución. |
| Versiones exactas de aquella ejecución | No acreditadas. Los notebooks muestran kernels Python 3.12.3 y 3.13.5. |

El entorno actual `fin-forecasting` contiene XGBoost 3.0.5, pandas 2.3.3,
NumPy 2.3.4, scikit-learn 1.7.2 y statsmodels 0.14.5. Son candidatos de entorno,
no prueba del entorno usado al generar las predicciones. El entorno del backend
utilizado para tests tiene pandas 3.0.2, NumPy 2.4.4 y no tiene XGBoost instalado.
No se instalaron dependencias ni se modificó `requirements.txt`.

Parámetros explícitos recuperados: 300 árboles, profundidad 3, learning rate
0,05, subsample 0,8, colsample_bytree 0,8, `multi:softprob`, `mlogloss`, semilla
42 y `n_jobs=-1`. No se inventan valores de `tree_method`, `base_score`, versión
de backend numérico ni otros defaults no registrados.

## Código reutilizado y cambios mínimos

| Componente | Integración |
| --- | --- |
| Mapping del Sprint 1A | Reutilizado y validado contra sus estadísticas CVaR; se rechaza el mapping fijo antiguo. |
| Desfase de exposición | Se reutiliza `apply_shifted_exposure` una vez dentro de OOS. |
| Métricas y drawdown actuales | Reutilizados; se añaden Sharpe, ratio retorno/CVaR, costes y turnover en funciones nuevas. |
| `data/loaders.py` | Solo se añade `load_ml_predictions`; no cambia ningún loader previo. |
| `ml/config.py` | Orden fijo de once features, muestras y parámetros explícitos, sin constructor que entrene. |
| `ml/data.py` | Ensamblado uno a uno, validación estricta, target siguiente sesión y preparación separada de train/evaluación. |
| `ml/inference.py` | Aplicación de clasificador ya entrenado y carga nativa JSON/UBJ con hash y metadatos. |
| `ml/evaluation.py` | Métricas de clasificación desde predicciones históricas, sin estimación. |
| `backtesting/ml_backtest.py` | Hard, ponderación probabilística, costes, turnover y comparación por fechas comunes. |
| `backtesting/strategy_service.py` | Selector interno compatible para consumo futuro desde rutas existentes. |

FastAPI, sus rutas y esquemas públicos, `main.py`, Streamlit y Docker permanecen
intactos. El servicio interno conserva Regime-based como opción por defecto.
No se ha activado ningún selector HTTP nuevo ni se anuncian resultados nuevos
en las pantallas. Las probabilidades ML conservan `proba_*`: no se reinterpretan
los campos Markov `p_regime_*`.

## Separación temporal y de responsabilidades

`prepare_features` exige las once columnas numéricas finitas en orden fijo,
fechas diarias válidas, únicas y ordenadas. No convierte strings numéricos, no
descarta columnas/filas ni reordena sesiones silenciosamente. `assemble_features`
reproduce el join por fecha del notebook, exigiendo cobertura completa.

`build_next_regime_target` añade `target_date` y `regime_t_plus_1`. Conserva la
última observación sin etiqueta: la inferencia diaria no necesita conocer el
futuro. `evaluation_rows` selecciona OOS etiquetado. `training_rows` solo prepara
datos y exige una política explícita: `historical_tfm` conserva la frontera
original; `causal` excluye objetivos que alcanzan test. No hay política implícita
ni llamada a `fit`. La selección definitiva sigue pendiente de aprobación.

La inferencia valida muestra, features y sus metadatos, classes_, probabilidades,
predicción y fecha de información máxima del entrenamiento. `trained_through`
debe incluir la fecha máxima de las etiquetas conocidas, no solo la última
fecha de features (especialmente importante para la frontera histórica).
La asociación de columnas se hace con `classes_`, no con etiquetas económicas.

`load_xgboost_model` solo permite JSON/UBJ nativo, con metadatos de muestra,
cutoff, features, clases, SHA-256 y versión XGBoost. Rechaza una versión distinta
antes de aplicar el modelo. No usa pickle, no instala librerías y no entrena.
La carga real y la inferencia XGBoost están pendientes de un artefacto real y
un runtime autorizado; los tests de inferencia utilizan un doble explícito.

## Estrategias y fidelidad contable

- Hard: mapping CVaR aplicado a la clase predicha para la sesión siguiente.
- Probabilística: suma de `proba_k * exposición_k` en el orden del mapping TFM.
- Exposición ejecutada: señal anterior, con una única sesión de desfase; se
  descarta la primera fila OOS como en el TFM.
- Retorno: exposición multiplicada por retorno logarítmico; capital mediante
  exponencial de suma; drawdown con la convención histórica existente.
- Costes: 0,001 por variación absoluta, primera variación cero, sin coste de
  entrada/salida; Buy & Hold cero costes.
- Turnover efectivo: cambio >0,01 solo para recuento; no elimina operaciones.
- Los objetivos futuros y el régimen observado no intervienen en decisiones ML.

No se corrigen silenciosamente aproximaciones contables o decisiones pendientes.

## Equivalencia verificada

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B scripts/check_ml_equivalence.py
```

El verificador solo imprime JSON. Lee fixtures, reconstruye todo en memoria y
compara fechas, todas las columnas originales del backtest, métricas brutas y
netas, turnover y clasificación. No necesita el repositorio TFM ni XGBoost
para las nuevas pruebas de replay. El test local opcional del Sprint 1A sigue
verificando las estadísticas originales si está disponible el TFM.

Resultado de esta ejecución: 42 pruebas superadas (14 de Sprint 1A y 28 nuevas),
sin omisiones. `git diff --check` no detectó errores. La comprobación de SHA-256
de 193 archivos protegidos antes/después confirmó que no cambiaron el TFM,
los datos operativos, el dashboard, la entrada FastAPI ni Docker. No se arrancó
ningún servicio; el transporte HTTP y la inferencia con XGBoost real no se
declaran verificados.

| Resultado | MAIN | ROBUST |
| --- | --- | --- |
| Predicciones | 1.376 | 1.633 |
| Filas de backtest ML | 1.375 | 1.632 |
| Inicio común | 05/01/2021 | 03/01/2020 |
| Fin común | 21/05/2026 | 21/05/2026 |
| Accuracy | 0,9120639534883721 | 0,8848744641763625 |
| Balanced accuracy | 0,7803323085931781 | 0,8164092511375646 |
| Stress recall | 0,5151515151515151 | 0,6583333333333333 |
| Error diario máximo | 4,44e-16 | 4,44e-16 |
| Error máximo métricas costes | 4,48e-13 | 4,20e-13 |
| Error máximo turnover | 7,11e-15 | 8,68e-17 |
| Error máximo métricas conjuntas | 1,07e-14 | 8,89e-15 |

Tolerancia numérica: `atol=1e-12`, `rtol=1e-10`. Fechas y clases se contrastan
exactamente. La lectura de CSV y el orden de las operaciones de coma flotante
explican diferencias de esta magnitud; no se alteran ni renormalizan probabilidades
para forzar coincidencias. Las tablas de clasificación publicadas tienen tres
decimales: se comparan con tolerancia de redondeo 0,0005 y además con las métricas
exactas del output guardado.

Discrepancias registradas, no corregidas en el TFM:

1. Regime-based conserva el 22/05/2026; ML termina el 21. La comparación conjunta
   elimina explícitamente esa sesión y recalcula métricas de las cuatro estrategias.
2. Las tablas netas conjuntas originales mezclan esos periodos. La equivalencia
   neta de las estrategias ML se acredita contra sus tablas propias; no se declara
   corregida la tabla conjunta ni su diferencia Regime-based.
3. La frontera train/target sigue siendo una decisión abierta, separada de este replay.
4. El maestro de Git permite recuperar un candidato de inputs, pero no equivale
   a recuperar el entrenamiento del modelo ni el snapshot completo de mayo.

## Próximo bloque: actualización automática existente

1. Resolver referencia de features y política de frontera; recuperar modelos
   reales o solicitar autorización explícita para entrenarlos por separado.
2. Registrar MAIN/ROBUST con features, clases, parámetros efectivos, versiones,
   cutoff informativo y hash. No reentrenar dentro del proceso diario.
3. Ampliar `run_daily_update.py` para producir las once features y aplicar modelos
   congelados. Actualizar también Markov por filtrado con parámetros persistidos,
   sin reajustarlo a diario.
4. Conectar esas salidas con `run_full_pipeline.py` y el servicio de estrategias,
   usando directorio de staging y validaciones antes de publicar una versión.
5. Mantener los contratos actuales como opción por defecto; revisar una extensión
   aditiva para selección de estrategia y probabilidades ML explícitas. No llenar
   `p_regime_*` con probabilidades ML de distinto significado.
6. Reutilizar las pestañas de backtesting/cola actuales con un selector mínimo;
   mostrar fecha efectiva, procedencia y estado de actualización, sin rediseño.
7. Proteger `/run-update`, impedir concurrencia y publicar los artefactos del
   workflow en el despliegue. Añadir readiness y compartir figuras con la
   configuración Docker existente en un bloque posterior.

Se detiene este sprint antes de entrenamiento, regeneración de CSV operativos,
despliegue o commits. Los resultados que sirve hoy la aplicación siguen siendo
los artefactos anteriores: este bloque añade capacidad al motor, no activa su
actualización pública.
