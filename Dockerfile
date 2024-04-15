FROM python:3.11.4-slim-buster

# Install Opus
RUN apt-get update && apt-get install -y git

WORKDIR /kexobot

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --no-deps wavelink==2.6.5
# RUN pip install --no-cache-dir --no-deps git+https://github.com/PythonistaGuild/Wavelink

COPY . .

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
EXPOSE 8000
EXPOSE 2333

CMD ["python", "KexoBOT.py"]
