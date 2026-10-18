FROM python:3.12-slim

# Hugging Face Spaces run containers as user 1000; owning everything as that user keeps the
# image working there and with docker compose alike.
RUN useradd -m -u 1000 user && mkdir -p /app /models && chown -R user /app /models
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    NLP_MODE=hf
WORKDIR /app

COPY --chown=user requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt \
 && pip install --no-cache-dir --user -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY --chown=user . .

# Download the models into the image so the app never needs the network at run time.
RUN python -c "from app.nlp import hf; hf.warmup(background=False); assert hf.ready(), hf._state"
# Integrity detector (pinned, label mapping verified during download). The feature stays off until
# AI_INTEGRITY_ENABLED=true is set on the host.
RUN python -m scripts.download_integrity_model /models/ai-text-detector-modernbert
ENV HF_HUB_OFFLINE=1 \
    AI_INTEGRITY_MODEL_PATH=/models/ai-text-detector-modernbert

# DATABASE_URL (PostgreSQL, e.g. Neon) must be set by the host; PORT optionally.
EXPOSE 8000
# Seed is idempotent: first start creates the demo data, later starts keep it.
# Proxy headers: behind Vercel / Hugging Face the client address comes from X-Forwarded-For.
CMD ["sh", "-c", "python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
