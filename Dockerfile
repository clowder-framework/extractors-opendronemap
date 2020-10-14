FROM opendronemap/odm:2.0.0

ARG VERSION="unknown"
ARG BUILDNUMBER="unknown"
ARG GITSHA1="unknown"

# environemnt variables
ENV VERSION=${VERSION} \
    BUILDNUMBER=${BUILDNUMBER} \
    GITSHA1=${GITSHA1} \
    RABBITMQ_QUEUE="ncsa.clamav"

WORKDIR /extractor

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY *.py extractor_info.json settings.yaml ./
CMD python3 opendrone_stitch.py
