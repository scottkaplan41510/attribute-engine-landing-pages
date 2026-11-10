FROM mcr.microsoft.com/playwright/python:v1.64.0-noble
WORKDIR /app
RUN apt-get update -qq && apt-get install -y -qq git > /dev/null
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir -q .
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
CMD ["sh", "-c", "uvicorn website_attribute_finder.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
