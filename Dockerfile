# ---- builder: compila dlib y arma el venv con todas las deps ----
FROM python:3.12 AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY webapp/requirements.txt webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# ---- final: runtime liviano ----
FROM python:3.12-slim

WORKDIR /app

# dlib se compila con soporte de GUI (enlaza contra libX11) en el stage
# builder; sin esta librería en el runtime, el import falla en silencio
# y todo el sistema cae al detector Haar + embedding fallback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

# Modelos dlib (landmarks + embeddings) usados también por la Raspberry Pi,
# para que ambos lados generen embeddings 128-dim comparables entre sí.
RUN python download_models.py

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:$PORT webapp.wsgi:app"]
