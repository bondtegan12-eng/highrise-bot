FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "highrise", "bot:TeleportBot", "64a094a74134ad0fd77b8734", "2c001cb06c4370e639be2d7a24cf4e7a0a860ef708d45d11cde0960653d0e8a6"]
