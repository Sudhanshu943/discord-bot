FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U yt-dlp

COPY . .

CMD ["python", "music.py"]
```

This installs Node.js v20 (LTS) instead of the old Debian default which is usually v12 or older.

After rebuilding check the Railway build logs — you should see:
```
## Installing Node.js v20