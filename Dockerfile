FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --upgrade pip \
    && pip install -r requirements/prod.txt

COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm --prefix frontend ci

COPY . .

# Build the React app before collectstatic so WhiteNoise picks up frontend/dist (see
# config/settings/base.py's WHITENOISE_ROOT and core/views.py's SPAView).
RUN npm --prefix frontend run build
RUN python manage.py collectstatic --noinput --settings=config.settings.prod || true

EXPOSE 8000

# Served over ASGI (not WSGI) so the same process handles the chat/notification
# WebSocket endpoints alongside the regular REST API.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
