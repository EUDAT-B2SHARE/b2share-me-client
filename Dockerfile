FROM python:3
MAINTAINER jani.heikkinen@csc.fi

RUN apt-get update
RUN apt-get install -y libhdf5-dev

WORKDIR /app

COPY Consumer.py Producer.py EiscatB2SHAREClient.py B2SHAREClient.py configuration.py requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

CMD [ "python", "EiscatB2SHAREClient.py" ]
