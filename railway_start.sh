#!/bin/bash
# Arranque del contenedor en Railway.
# El plan free de Railway duerme MySQL cuando esta inactivo (y una
# conexion interna no lo despierta), asi que se reintenta la BD en vez de
# romper el arranque. Si la BD no responde, la app se levanta igual
# (las paginas que tocan BD daran 500, pero la app existe y se ve el log).
set -u

i=0
until python manage.py migrate; do
    i=$((i + 1))
    if [ "$i" -ge 12 ]; then
        echo "BD no responde tras $i intentos; se arranca gunicorn igual."
        break
    fi
    echo "BD no lista (intento $i); reintento en 5s..."
    sleep 5
done

python manage.py seed_demo || echo "seed_demo fallo; revisar error arriba."
python manage.py reentrenar_ia || true
python manage.py collectstatic --noinput || true

exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
