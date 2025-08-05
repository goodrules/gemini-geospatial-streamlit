FROM python:3.13
EXPOSE 8080
WORKDIR /app
COPY . .
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD streamlit run --server.port 8080 --server.enableCORS false app.py 