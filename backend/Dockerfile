FROM python:3.12-slim

WORKDIR /srv

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# backend/ と ml/ を同じルート配下に置き、`backend.app.main:app` として起動する
COPY backend ./backend
COPY ml ./ml
COPY data ./data

ENV PYTHONPATH=/srv
EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
