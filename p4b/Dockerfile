# The only executed code is RISU's own Python scanner and audit harness.
# Original OpenAPI files are mounted read-only. No external project code.
FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN python -m pip install --disable-pip-version-check --no-cache-dir PyYAML==6.0.2 \
 && python -m pip check
WORKDIR /opt/risu
COPY p4a /opt/risu/p4a
COPY p4b /opt/risu/p4b
COPY dist/risu_v096_baseline /opt/risu/dist/risu_v096_baseline
COPY dist/risu_v09_source /opt/risu/dist/risu_v09_source
RUN chmod -R a+rX /opt/risu
ENV PYTHONPATH=/opt/risu
ENV HOME=/tmp TMPDIR=/tmp
USER 65534:65534
ENTRYPOINT ["python","-B","/opt/risu/p4b/paired_run.py"]
