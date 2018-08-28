FROM ubuntu:16.04
MAINTAINER Flywheel <support@flywheel.io>

RUN apt-get update && apt-get install -y dcmtk jq unzip python2.7 python-pip

RUN pip2 install flywheel-sdk
RUN pip2 install pydicom>=1.1.0

# Make directory for flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
COPY run ${FLYWHEEL}/run
COPY download_dicoms.py ${FLYWHEEL}/download_dicoms.py
COPY tagger.py ${FLYWHEEL}/tagger.py
COPY manifest.json ${FLYWHEEL}/manifest.json

RUN chmod +x ${FLYWHEEL}/run
