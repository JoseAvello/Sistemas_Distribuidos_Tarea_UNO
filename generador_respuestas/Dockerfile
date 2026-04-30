FROM python:3.11-slim
WORKDIR /app
RUN pip install flask requests
COPY app.py .
# El CSV se monta como volumen en /datos
CMD ["python", "app.py"]
