FROM python:3.11-slim

WORKDIR /app

# tesseract-ocr is the OCR engine used by the extraction pipeline (Step 4).
# Add tesseract-ocr-hin (or other tesseract-ocr-<lang> packages) here too
# if labels need a regional-language OCR pass alongside English.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
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
