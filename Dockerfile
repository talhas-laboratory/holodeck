FROM python:3.13-slim

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin holodeck

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /data && chown holodeck:holodeck /data

USER holodeck
ENV HOLODECK_DATABASE=/data/holodeck.db
EXPOSE 8787

CMD ["holodeck", "serve", "--host", "0.0.0.0", "--port", "8787", "--database", "/data/holodeck.db", "--insecure-bind"]
