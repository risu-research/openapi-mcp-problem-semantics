# Only vetted RISU code is executable. External OpenAPI inputs are mounted
# read-only at runtime; no user credentials or source project code imported.
FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN python -m pip install --disable-pip-version-check --no-cache-dir PyYAML==6.0.2 \
 && python -m pip check
WORKDIR /opt/risu
COPY p4a /opt/risu/p4a
COPY dist/risu_v09_source /opt/risu/dist/risu_v09_source
RUN chmod -R a+rX /opt/risu
ENV PYTHONPATH=/opt/risu/dist/risu_v09_source
ENV HOME=/tmp TMPDIR=/tmp
USER 65534:65534
ENTRYPOINT ["python","-B","/opt/risu/p4a/run_offline.py"]
