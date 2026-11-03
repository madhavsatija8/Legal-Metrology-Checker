FROM python:3.11-slim

WORKDIR /app

# tesseract-ocr is the OCR engine used by the extraction pipeline (Step 4).
# tesseract-ocr-hin is installed because the pipeline defaults to
# lang="eng+hin" (backend/app/ocr/extraction.py) — most Indian packaging
# carries a Devanagari declaration alongside the English one. Add further
# tesseract-ocr-<lang> packages here for other regional scripts as needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
