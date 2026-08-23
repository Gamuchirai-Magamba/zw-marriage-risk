# Lean runtime: the API serves frozen JSON, so none of the modelling
# stack (statsmodels, geopandas, scikit-learn) is installed here.
FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# --no-deps: we want the module, not its modelling dependencies
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

# Only district-level aggregates. Microdata never enters the image;
# .dockerignore blocks it from the build context as well.
COPY --chown=app:app app_data ./app_data

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"

CMD ["sh", "-c", "uvicorn zw_marriage_risk.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
