# Dockerfile for dicom-send gear

FROM ubuntu:20.04

MAINTAINER Flywheel <support@flywheel.io>

# Python & # DCMTK setup
RUN apt-get update && apt-get install -y software-properties-common \
                                         dcmtk=3.6.4-2.1build2
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.8 python3-pip
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt

# Flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
WORKDIR ${FLYWHEEL}

# Copy gear specific scripts
COPY manifest.json ${FLYWHEEL}/manifest.json
ADD utils ${FLYWHEEL}/utils
COPY run.py ${FLYWHEEL}/run.py
RUN chmod +x ${FLYWHEEL}/run.py

COPY storescu.cfg /tmp/storescu.cfg
ADD tests/assets ${FLYWHEEL}/test_data

COPY tests/test_send.sh ${FLYWHEEL}/test_send.sh
RUN chmod +x ${FLYWHEEL}/test_send.sh

# ENTRYPOINT /bin/bash
CMD ["/bin/bash"]
