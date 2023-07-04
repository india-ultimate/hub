FROM python:3.11

RUN apt-get update \
    && apt-get install --no-install-recommends --assume-yes nginx yarnpkg sudo \
    && rm -r /var/lib/apt/lists /var/cache/apt

RUN useradd --create-home --shell /bin/bash --gid users --groups sudo user
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
ENV HOME=/home/user
ENV APP=$HOME/app
USER user

RUN mkdir $HOME/app
WORKDIR $APP

COPY --chown=user:users requirements.txt $APP/requirements.txt
RUN pip install -r requirements.txt

RUN mkdir $APP/frontend
WORKDIR $APP/frontend

COPY --chown=user:users frontend/yarn.lock yarn.lock
COPY --chown=user:users frontend/package.json package.json
RUN yarnpkg

COPY --chown=user:users frontend .
RUN yarnpkg run build
RUN rm -rf node_modules/

WORKDIR $APP

ARG DJANGO_SETTINGS_MODULE
COPY --chown=user:users manage.py .
COPY --chown=user:users server server
COPY --chown=user:users hub hub
RUN python manage.py collectstatic --no-input

USER root
RUN mkdir -p /var/www/hub/static/
RUN cp -a /tmp/static/ /var/www/hub/
COPY deploy/nginx.conf /etc/nginx/sites-enabled/hub.conf
RUN mkdir -p /data
RUN chown -hR user:users /data

COPY --chown=user:users deploy deploy
USER user
ENTRYPOINT deploy/start.sh
