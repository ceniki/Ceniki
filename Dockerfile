# Uporaba uradne slike Python
FROM python:3.9-slim

# Nastavitev delovnega direktorija v kontejnerju
WORKDIR /app

# Kopiranje datotek z zahtevami in namestitev knjižnic
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Kopiranje preostale aplikacijske kode
COPY . .

# Izpostavitev porta 8080 (privzeti port za Fly.io)
EXPOSE 8080

# Določitev ukaza za zagon aplikacije z uporabo Gunicorna
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
