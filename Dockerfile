FROM python:3.14-slim-bookworm
ENV PYTHONUNBUFFERED 1
WORKDIR /code

#install ipykernel package
RUN pip install --upgrade pip
RUN pip install ipykernel
RUN python -m pip install Django

#install git
RUN apt-get update && apt-get install -y git

ARG GIT_COMMIT_SHA
ENV GIT_COMMIT_SHA=$GIT_COMMIT_SHA
