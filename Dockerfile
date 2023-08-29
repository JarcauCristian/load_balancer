FROM python:3.9-slim-bullseye

WORKDIR /app

COPY . .

RUN pip install --trusted-host pypi.python.org -r requirements.txt

ADD https://dl.min.io/client/mc/release/linux-amd64/mc mc

RUN chmod +x /app/mc

ENV PATH="${PATH}:/app"

EXPOSE 8000

CMD python3 main.py
