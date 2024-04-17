FROM --platform=linux/amd64 python:3.9

WORKDIR /app

COPY twitter.py .

COPY config.ini .

COPY templates /app/templates

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

CMD ["python", "twitter.py"]
