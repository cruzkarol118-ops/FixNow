# FixNow
Plataforma digital que conecta de manera rápida y confiable a personas que necesitan un servicio técnico en el hogar - como electricidad, plomería o soporte tecnológico - con técnicos disponibles cerca de su ubicación.

## Arranque en Windows (desde cero)

Requisitos: Python 3.12+, MariaDB/MySQL corriendo en `127.0.0.1:3306`
(nota: se necesita **MySQL 10.5+ / MariaDB 10.5+**; el proyecto usa el modo
estricto `STRICT_TRANS_TABLES` en la conexión).

```bat
cd FixNow
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM crea la base de datos vacía (una sola vez):
mysql -u root -e "CREATE DATABASE IF NOT EXISTS fixnow_db CHARACTER SET utf8mb4;"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Abre http://127.0.0.1:8000/ — con solo el README el repo arranca.

Verificaciones:

```bat
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

## Credenciales demo

Carga datos de prueba idempotentes (si ya existen, los borra y recrea):

```bat
.\.venv\Scripts\python.exe manage.py seed_demo
```

Todos usan la contraseña **`Demo123!`**:

| Usuario | Correo | Rol |
|---|---|---|
| Admin | admin@fixnow.co | administrador (staff) |
| Cliente 1 | cliente1@demo.fixnow.co | cliente |
| Cliente 2 | cliente2@demo.fixnow.co | cliente |
| Técnico 1 | tecnico1@demo.fixnow.co | plomería |
| Técnico 2 | tecnico2@demo.fixnow.co | electricidad |
| Técnico 3 | tecnico3@demo.fixnow.co | cerrajería |

Incluye 3 solicitudes en distintos estados (pendiente, en curso, finalizada)
y 1 calificación de 5★. Para ver la ayuda: `manage.py seed_demo --help`.

Usuarios QA (ya existen en el entorno de desarrollo): cliente@test.co,
tecnico@test.co, admin@test.co, contraseña `Clave123!`.

## IA (Bloque F)

- Clasificador de categoría (FN-3): Naive Bayes + TF-IDF (`core/ia.py`,
  requiere `scikit-learn`). En "Nueva solicitud" el botón
  **Sugerir categoría con IA** preselecciona la categoría y muestra
  "IA sugiere: X". Sin scikit-learn, el formulario funciona igual.
- Sentimiento (FN-7): por léxico en español, sin dependencias. Un insulto
  o un 5★ con texto muy negativo deja la calificación
  **en revisión** y avisa al admin.
