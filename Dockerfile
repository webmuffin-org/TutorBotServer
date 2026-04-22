FROM python:3.12

RUN mkdir -p /code
WORKDIR /code

COPY . /code

RUN pip install --upgrade pip 
RUN pip install --no-cache-dir --upgrade -r /code/requirements-unix.txt


EXPOSE 3000

CMD ["python", "TutorBot_Server.py"]