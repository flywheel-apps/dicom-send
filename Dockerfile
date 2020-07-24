# Dockerfile for dicom-send gear

FROM ubuntu:20.04

MAINTAINER Flywheel <support@flywheel.io>

# Python setup
RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.8 python3-pip
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt

# DCMTK setup
RUN apt-get install -y dcmtk=3.6.4-2.1build2

# Flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
WORKDIR ${FLYWHEEL}

# Copy gear specific scripts
COPY manifest.json ${FLYWHEEL}/manifest.json
ADD utils ${FLYWHEEL}/utils
COPY run.py ${FLYWHEEL}/run.py
RUN chmod +x ${FLYWHEEL}/run.py
