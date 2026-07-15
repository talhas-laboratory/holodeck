FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENV HOLODECK_DATABASE=/data/holodeck.db
EXPOSE 8787
CMD ["holodeck", "serve", "--host", "0.0.0.0", "--port", "8787", "--database", "/data/holodeck.db"]
