# Registro de evidencias · CanchaYa (Desarrollo Seguro, UCP)

Cada evidencia apoya una amenaza del modelo (`seguridad/lab1/LAB1.md`) o una pieza del pipeline. Las capturas son del 21 de noviembre de 2026.

## T2 · Cancelación tardía con reembolso (lógica de negocio)

| ID | Qué demuestra | Archivo |
|---|---|---|
| E04 | La prueba nueva falla en local antes del arreglo: la API responde 200 donde el requisito exige 409. Es la falla reproducida. | `E04-local-prueba-t2-en-rojo.txt` |
| E02 | En el PR #3, con solo la prueba, `CI / test` queda en rojo y está marcado como requerido. Auditgate pasa en verde: el SAST no ve una falla de lógica de negocio. | `E02-pr3-rojo-ci-test-required.png` |
| E03 | El mismo PR en rojo con el merge bloqueado y sin opción de saltarse las reglas. El triage con IA comenta "Sin hallazgos": como ningún escáner reportó nada, no tuvo qué clasificar (el agente solo revisa lo que encuentran los escáneres). | `E03-pr3-rojo-sin-bypass-triage-ia.png` |
| E05 | Con el arreglo, en local pasan las 29 pruebas, con cobertura de 91 % y formato correcto. | `E05-local-29-pruebas-cobertura-91.png` |
| E06 | El PR #3 en verde, listo para merge. SonarQube Cloud tampoco reporta hallazgos (0 new issues). | `E06-pr3-verde-sonarqube.png` |
| E07 | Historial de `main` después del merge: commit de la prueba, del arreglo y de los documentos. | `E07-main-historial-tras-merge-pr3.png` |
| E08 | Ensayo de la demo: una regresión que quita el control (PR #4) y su revert; al final todos los checks en verde. | `E08-ensayo-demo-regresion-y-revert.png` |
| E09 | El rojo de la regresión quedó registrado en GitHub (`test: failure` en el commit `0973181`). | `E09-ensayo-demo-rojo-registrado.png` |

PR: https://github.com/mateoaamm/canchaya/pull/3 · Demo: https://github.com/mateoaamm/canchaya/pull/4

## T1 · Cuentas del seed con contraseñas publicadas

| ID | Qué demuestra | Archivo |
|---|---|---|
| E10 | `/health` en producción se queda cargando: la API no logra arrancar. | `E10-render-health-no-arranca.png` |
| E11 | El panel de Render muestra un solo recurso, `canchaya-api` en *Failed service*. La base `canchaya-db`, donde estaban las cuentas del seed, ya no existe porque expiró el plan gratuito. | `E11-render-panel-sin-base-de-datos.png` |
| E12 | `canchaya-api` suspendido en Render (aparece la opción *Resume Web Service*): no puede volver a arrancar por accidente con una base nueva. | `E12-render-api-suspendida.png` |
| E13 | En el PR #5, el commit que solo trae la prueba (`0422ccb`) queda en rojo: `test: failure`. | `E13-pr5-t1-rojo-registrado.png` |
| E14 | Con el arreglo, en local pasan 32 pruebas, con cobertura de 91 %. El seed real se bloquea con `APP_ENV=production` y contra una base remota (salida 1 en ambos casos). | `E14-local-t1-32-pruebas-seed-bloqueado.png` |
| E15 | El PR #5 en verde: todos los checks pasan con el arreglo. | `E15-pr-t1-verde-checks.png` |
| E16 | Merge del PR #5 en `main` (`8e1afcd`), con el commit de la prueba y el del arreglo. | `E16-merge-pr5-t1.txt` |

PR: https://github.com/mateoaamm/canchaya/pull/5

## Pipeline y gate

| ID | Qué demuestra | Archivo |
|---|---|---|
| E01 | Protección de `main`: `test` y `auditgate / Security Gate` son checks requeridos. Después se activó además "Do not allow bypassing the above settings"; E03 muestra el efecto. | `E01-proteccion-rama-checks-requeridos.png` |
