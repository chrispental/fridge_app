# Official Playwright browser image; keep Python client and browsers aligned.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
RUN pip install --no-cache-dir playwright==1.63.0
COPY mcp_local_smoke.py /smoke.py
CMD ["python", "/smoke.py"]
