FROM python:alpine
RUN apk add --no-cache git
COPY requirements.txt /app/
WORKDIR /app
RUN pip install -r requirements.txt
COPY app.py /app/ 
USER 1001
ENTRYPOINT ["python"]
CMD ["app.py"]
