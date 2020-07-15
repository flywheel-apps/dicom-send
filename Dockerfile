FROM ubuntu:16.04
MAINTAINER Flywheel <support@flywheel.io>

RUN apt-get update && apt-get install -y dcmtk jq unzip python2.7 python-pip

COPY requirements.txt ./requirements.txt
RUN pip2 install -r requirements.txt

# Make directory for flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
COPY run ${FLYWHEEL}/run
COPY download_dicoms.py ${FLYWHEEL}/download_dicoms.py
COPY tagger.py ${FLYWHEEL}/tagger.py
COPY manifest.json ${FLYWHEEL}/manifest.json

RUN chmod +x ${FLYWHEEL}/run
