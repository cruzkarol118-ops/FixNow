"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os
import time

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()


# ------------------------------------------------------------------
# Bootstrap de producción dentro de la app: garantiza migraciones y datos
# demo sin importar el comando con que arranque el servidor (Railway ignora
# comandos custom, pero config.wsgi siempre lo importa gunicorn).
# Solo corre con DEBUG=False; en desarrollo local no toca nada.
#
# Layerbase suspende la BD tras inactividad y despierta al conectar en frío
# (~20 s): por eso se reintentan los pasos en vez de romper el arranque.
def _bootstrap_bdd():
    try:
        from django.core.management import call_command
        from django.db import connection, OperationalError

        fin = time.time() + 25
        while time.time() < fin:
            try:
                connection.cursor().execute("SELECT 1")
                break
            except OperationalError:
                time.sleep(4)
        else:
            print("Bootstrap: BD no respondió; la app arranca igual y se "
                  "reintenta en cada request.")
            return

        call_command("migrate")
        from core.models import Usuario

        if not Usuario.objects.filter(correo="admin@test.co").exists():
            call_command("seed_demo")
            print("Bootstrap: usuarios demo creados.")
        else:
            print("Bootstrap: usuarios demo ya existen.")
    except Exception as exc:  # nunca tumbar la app por el bootstrap
        print(f"Bootstrap omitido (la app sigue arriba): {exc!r}")


from django.conf import settings

if not settings.DEBUG:
    _bootstrap_bdd()
