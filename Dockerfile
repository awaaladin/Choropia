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

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build the web frontend's CSS before collectstatic so the compiled output gets picked up.
RUN npm run build
RUN python manage.py collectstatic --noinput --settings=config.settings.prod || true

EXPOSE 8000

# Served over ASGI (not WSGI) so the same process handles the chat/notification
# WebSocket endpoints alongside the regular REST API.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
