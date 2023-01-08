FROM python:3.10.7-slim-buster

EXPOSE 8501

WORKDIR /usr

COPY requirements.txt /usr/requirements.txt

RUN pip install -r /usr/requirements.txt

COPY src /usr/src

ENV PYTHONPATH "${PYTHONPATH}:/usr/src"


# CMD ["streamlit", "run", "src/app.py",  "--server.port=8501", "--server.address=0.0.0.0"]
# ENTRYPOINT ["streamlit", "run"]
# CMD ["src/app.py"]
ENTRYPOINT ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
