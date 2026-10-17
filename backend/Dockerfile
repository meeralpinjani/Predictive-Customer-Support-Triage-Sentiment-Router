FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    NLP_MODE=hf \
    DATABASE_URL=sqlite:////data/triage.db \
    UPLOAD_DIR=/data/uploads

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .

# Download the models into the image so the demo never needs the network.
RUN python -c "from app.nlp import hf; hf.warmup(background=False); assert hf.ready(), hf._state" \
 && mkdir -p /data
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
# Seed is idempotent: first start creates the demo data, later starts keep it.
CMD ["sh", "-c", "python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
