# CanchaYa ⚽

API de reservas de canchas de fútbol sintéticas, construida con **FastAPI + PostgreSQL** con el rigor de un proyecto laboral real: autenticación JWT con refresh tokens, RBAC, migraciones con Alembic, suite de tests contra Postgres real y un pipeline de CI que bloquea el merge si algo no pasa.

El objetivo de este proyecto no son las features, sino las **prácticas de ingeniería** que rodean al código. La pieza central es la **prevención de doble reserva a nivel de base de datos**: el problema clásico donde dos personas piden el mismo horario al mismo tiempo y solo una debe ganar.

---

## Tabla de contenido

- [Stack](#stack)
- [Arranque rápido](#arranque-rápido)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Conceptos clave](#conceptos-clave)
  - [El problema de la doble reserva](#el-problema-de-la-doble-reserva)
  - [Autenticación y tokens](#autenticación-y-tokens)
  - [RBAC y ownership](#rbac-y-ownership)
  - [Zonas horarias](#zonas-horarias)
- [Endpoints](#endpoints)
- [Tests](#tests)
- [Integración continua (CI)](#integración-continua-ci)
- [Mapa de milestones](#mapa-de-milestones)
- [Notas de aprendizaje](#notas-de-aprendizaje)

---

## Stack

| Capa | Herramienta |
|------|-------------|
| Framework web | FastAPI |
| ORM | SQLAlchemy 2.0 (estilo `Mapped`) |
| Base de datos | PostgreSQL 16 |
| Driver | psycopg 3 |
| Migraciones | Alembic |
| Validación | Pydantic 2 |
| Auth | PyJWT + bcrypt |
| Tests | pytest + pytest-cov |
| Calidad | ruff (lint + format), mypy |
| CI | GitHub Actions |

---

## Arranque rápido

Requisitos: Python 3.11+ y Docker (o un Postgres local).

```bash
# 1. Clonar e instalar dependencias
pip install -e ".[dev]"

# 2. Configurar entorno
cp .env.example .env
#   genera un SECRET_KEY fuerte:
python -c "import secrets; print(secrets.token_urlsafe(48))"
#   y pégalo en .env

# 3. Levantar Postgres
docker compose up -d

# 4. Aplicar migraciones
alembic upgrade head

# 5. Arrancar la API
uvicorn app.main:app --reload
```

Abre la documentación interactiva en **http://localhost:8000/docs**.

> Atajos: `make help` lista todos los comandos disponibles.

---

## Estructura del proyecto

```
canchaya/
├── app/
│   ├── main.py              # punto de entrada FastAPI
│   ├── enums.py             # enumeraciones del dominio
│   ├── core/
│   │   ├── config.py        # settings desde entorno (pydantic-settings)
│   │   ├── database.py      # engine, sesión, Base declarativa
│   │   └── security.py      # hashing bcrypt + tokens JWT
│   ├── models/              # tablas SQLAlchemy (ORM)
│   ├── schemas/             # contratos de entrada/salida (Pydantic)
│   ├── api/
│   │   ├── deps.py          # dependencias de auth y RBAC
│   │   └── routes/          # endpoints por dominio
│   └── services/
│       └── booking_service.py   # lógica de negocio de reservas
├── alembic/
│   └── versions/
│       ├── 0001_initial_schema.py            # esquema completo
│       └── 0002_booking_exclude_constraint.py # ⭐ constraint anti-doble-reserva
├── tests/                   # suite contra Postgres real
├── .github/workflows/ci.yml # pipeline de CI
├── docker-compose.yml       # Postgres para desarrollo
├── Makefile
└── pyproject.toml           # deps + config de ruff/mypy/pytest
```

La separación **routes → services → models** es deliberada: las rutas manejan HTTP y permisos, los servicios contienen la lógica de negocio (testeable sin HTTP), y los modelos solo describen datos.

---

## Conceptos clave

### El problema de la doble reserva

Es el corazón del proyecto. Imagina dos clientes pidiendo la misma cancha a las 6 pm exactamente al mismo tiempo:

```
Request A: consulta -> "libre" -> inserta reserva
Request B: consulta -> "libre" -> inserta reserva   ← ambos vieron "libre"
```

Un `if` en Python que consulta antes de insertar **no protege** bajo concurrencia: ambos requests consultan antes de que cualquiera inserte, ambos ven el horario libre, y ambos insertan. El bug aparece solo bajo carga, que es justo cuando más duele.

La solución es **defensa en profundidad, con dos capas**:

**Capa 1 — chequeo en código** (`app/services/booking_service.py`). Una query de solapamiento que da un `409 Conflict` amable antes de intentar insertar. Mejora la experiencia de usuario, pero **no es la garantía**.

**Capa 2 — constraint en la base de datos** (`alembic/versions/0002`). La garantía real. Un `EXCLUDE constraint` de PostgreSQL con índice GiST:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings
ADD CONSTRAINT no_double_booking
EXCLUDE USING gist (
    court_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status <> 'cancelled');
```

Esto le dice a Postgres: *no pueden coexistir dos filas con el mismo `court_id` y rangos de tiempo que se solapen (`&&`), salvo las canceladas*. La extensión `btree_gist` permite combinar la igualdad de `court_id` con el operador de solapamiento de rangos en un mismo índice. El `[)` hace que los intervalos sean cerrados-abiertos, así una reserva que termina a las 7 pm y otra que empieza a las 7 pm **no** se consideran solapadas.

Bajo concurrencia, cuando dos transacciones insertan rangos solapados, la segunda **se bloquea** esperando a la primera; cuando la primera confirma, la segunda recibe una `ExclusionViolation` y falla. Exactamente una gana. Siempre.

> El test `tests/test_bookings_concurrency.py` lanza dos hilos reales que insertan a la vez y verifica que exactamente uno gana y el otro recibe `ExclusionViolation`.

### Autenticación y tokens

Dos tipos de token con propósitos distintos:

- **Access token**: vida corta (15 min). Se manda en cada request (`Authorization: Bearer ...`). Si se filtra, caduca rápido.
- **Refresh token**: vida larga (7 días). Solo sirve para pedir un nuevo access token. Lleva un `jti` (id único) que **guardamos en BD** para poder revocarlo.

Por eso el **logout invalida de verdad** la sesión: marca el `jti` como revocado y `/auth/refresh` con ese token devuelve `401`. No depende de que el cliente "olvide" el token. Esto se prueba en `test_auth.py::test_logout_revokes_refresh_token`.

### RBAC y ownership

Tres roles con permisos genuinamente distintos:

| Rol | Puede |
|-----|-------|
| **Cliente** | Ver disponibilidad, crear y cancelar **sus** reservas |
| **Staff** | Gestionar reservas y confirmar pagos **de su sede** |
| **Admin** | Todo, más crear sedes, canchas y horarios |

La dependencia `require_roles(...)` valida el rol. Pero el rol no basta: un cliente no puede ver la reserva de **otro** cliente aunque ambos sean clientes. Eso es **autorización por ownership**, y prevenir el acceso a recursos ajenos por ID (un bug llamado **IDOR**) es de los fallos más comunes y graves en producción.

Detalle de diseño: cuando alguien pide un recurso que no le corresponde, devolvemos `404` (no `403`), para no revelar siquiera que ese recurso existe. Ver `test_rbac.py::test_client_cannot_see_other_clients_booking`.

### Zonas horarias

Regla de oro: **todo se guarda en UTC** (columnas `timestamptz`). Cada sede tiene su zona horaria IANA (ej. `America/Bogota`), que se usa para interpretar los horarios de atención y mostrar los slots. Los timestamps se aceptan y devuelven en ISO 8601 con offset. Esta separación (almacenar en UTC, presentar en local) evita la clase de bugs donde una reserva "se mueve" una hora según quién la mire.

---

## Endpoints

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| POST | `/auth/register` | público | Registro (crea cliente) |
| POST | `/auth/login` | público | Devuelve access + refresh |
| POST | `/auth/refresh` | público | Nuevo access token |
| POST | `/auth/logout` | público | Revoca el refresh token |
| GET | `/auth/me` | autenticado | Usuario actual |
| GET | `/venues` | autenticado | Lista sedes |
| POST | `/venues` | admin | Crear sede |
| GET | `/venues/{id}` | autenticado | Detalle de sede |
| POST | `/venues/courts` | admin | Crear cancha |
| GET | `/courts` | autenticado | Lista canchas (filtro `venue_id`) |
| POST | `/courts/{id}/availability` | admin | Definir horario de atención |
| GET | `/courts/{id}/availability` | autenticado | Slots libres de un día |
| POST | `/bookings` | cliente | Crear reserva |
| GET | `/bookings` | autenticado | Mis reservas (scope por rol) |
| GET | `/bookings/{id}` | dueño/staff/admin | Detalle de reserva |
| POST | `/bookings/{id}/cancel` | dueño/staff/admin | Cancelar |
| POST | `/bookings/{id}/confirm-payment` | staff/admin | Confirmar pago → reserva confirmada |
| GET | `/courts/{id}/bookings` | staff/admin | Vista de la sede |
| GET | `/health` | público | Health check |

---

## Tests

```bash
make test          # corre la suite
make cov           # con reporte de cobertura
```

**Decisión importante**: los tests corren contra **PostgreSQL real, no SQLite**. El corazón del proyecto (`EXCLUDE`, `tstzrange`, `btree_gist`) es específico de Postgres; testear contra otra base de datos ocultaría justo los bugs que más importan. El esquema se crea con las **mismas migraciones** que producción.

La BD de tests por defecto es `canchaya_test`:

```bash
createdb -h localhost -U canchaya canchaya_test   # o: make createdb
```

Cobertura actual: **~91%**, con 25 tests cubriendo auth, RBAC/IDOR, solapamiento en código, **concurrencia real a nivel de BD**, cálculo de slots y ciclo de vida de reservas.

---

## Integración continua (CI)

`.github/workflows/ci.yml` corre en cada push y Pull Request, levantando un Postgres idéntico al de los tests. El pipeline ejecuta, en orden:

1. `ruff check` — linter
2. `ruff format --check` — formato
3. `mypy app` — chequeo de tipos
4. `pytest --cov --cov-fail-under=80` — tests + cobertura mínima

Si **cualquier** paso falla, el build queda en rojo. Activando *branch protection* en GitHub (Settings → Branches), el merge a `main` se bloquea hasta que el CI pase. **Esa es la práctica que separa un proyecto de hobby de uno laboral**: el código no entra hasta que las pruebas pasan.

Para reproducir el pipeline completo en local: `make check`.

---

## Mapa de milestones

| Milestone | Dónde vive |
|-----------|-----------|
| 1. FastAPI + modelo + migración + auth JWT | `app/`, `alembic/versions/0001`, `app/api/routes/auth.py` |
| 2. Sedes, canchas y disponibilidad | `app/api/routes/venues.py`, `courts.py` |
| 3. Reserva con validación de solapamiento (código) | `app/services/booking_service.py`, `test_bookings_overlap.py` |
| 4. Constraint de exclusión + test de concurrencia | `alembic/versions/0002`, `test_bookings_concurrency.py` |
| 5. Cancelaciones, vista de staff, CI + cobertura | `app/api/routes/bookings.py`, `.github/workflows/ci.yml` |

---

## Notas de aprendizaje

Cosas que este proyecto te entrena y que en una entrevista o en el trabajo se notan:

- **La base de datos es tu última línea de defensa.** Las validaciones en código son para UX; las garantías de integridad van en la BD (constraints, no solo `if`).
- **Testea contra la misma tecnología que usas en producción.** SQLite en tests + Postgres en prod = bugs que no ves hasta que es tarde.
- **Las migraciones son código.** Reversibles, revisadas, versionadas. La 0002 enseña que puedes añadir constraints a tablas que ya existen.
- **Defensa en profundidad.** Capa de código *y* capa de BD; no una *o* la otra.
- **Secretos fuera del código.** Todo lo sensible entra por entorno y se valida al arrancar.
- **El CI es un contrato.** Verde = mergeable. Es lo que permite trabajar en equipo sin romper `main`.

### Ideas para seguir creciendo

- Tareas en segundo plano (Celery/RQ) para recordatorios de reserva.
- Logging estructurado y seguimiento de errores (Sentry).
- Rate limiting en `/auth/login`.
- Rotación de refresh tokens (invalidar el viejo al emitir uno nuevo).
- Dockerizar la propia API con un `Dockerfile` multi-stage.
