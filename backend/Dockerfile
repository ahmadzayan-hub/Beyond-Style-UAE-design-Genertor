# Beyond Style UAE — backend (P0 Golden Path slice)
# uharfbuzz/shapely ship manylinux wheels with bundled native libs
# (HarfBuzz, GEOS), so the image needs no system-level font/geometry deps.
FROM python:3.11.10-slim-bookworm

WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
