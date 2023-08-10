FROM python:3.11

RUN apt-get update \
    && apt-get install --no-install-recommends --assume-yes nginx yarnpkg sudo cron \
    && rm -r /var/lib/apt/lists /var/cache/apt

# Create a user
RUN useradd --create-home --shell /bin/bash --gid users --groups sudo user
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
ENV HOME=/home/user
ENV APP=$HOME/app
USER user

RUN mkdir $HOME/app
WORKDIR $APP

# Install Python dependencies
COPY --chown=user:users requirements.txt $APP/requirements.txt
RUN pip install -r requirements.txt
COPY --chown=user:users README.md .

RUN mkdir $APP/frontend
WORKDIR $APP/frontend

# Install JS/node dependencies
COPY --chown=user:users frontend/yarn.lock yarn.lock
COPY --chown=user:users frontend/package.json package.json
RUN yarnpkg

# Build frontend code
COPY --chown=user:users frontend .
RUN yarnpkg run build
RUN rm -rf node_modules/

WORKDIR $APP

# Build staticfiles
ARG DJANGO_SETTINGS_MODULE
COPY --chown=user:users manage.py .
COPY --chown=user:users server server
COPY --chown=user:users hub hub
RUN python manage.py collectstatic --no-input

# Setup staticfiles and Nginx
USER root
RUN mkdir -p /var/www/hub/
RUN cp -a $APP/staticfiles/ /var/www/hub/static/
COPY deploy/nginx.conf /etc/nginx/sites-enabled/hub.conf
RUN mkdir -p /data
RUN chown -hR user:users /data

COPY --chown=user:users deploy deploy
USER user

# Setup cron jobs
COPY --chown=user:users scripts/hourly.sh cron/hourly.sh
COPY --chown=user:users scripts/daily.sh cron/daily.sh
RUN crontab -l | { cat; cat deploy/crontab; echo ""; } | crontab -

ENTRYPOINT deploy/start.sh
