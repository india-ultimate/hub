# hub

[![CI Tests](https://github.com/india-ultimate/hub/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/india-ultimate/hub/actions/workflows/test.yml)

<!-- All the content from about:start to about:end appears in the About page -->
<!-- about:start -->

This is India ultimate's Membership and Payment Management Portal

The site is built using [Django](https://www.djangoproject.com/), [Django
Ninja](https://django-ninja.rest-framework.com/) and
[SolidJS](https://www.solidjs.com/). The code is licensed under the GNU AGPL
v3.0 License.

You can report issues on
[GitHub](https://github.com/india-ultimate/hub/issues),
[Zulip](https://upai.zulipchat.com/) or
[WhatsApp](http://bit.ly/India-Ultimate-Helpdesk).

<!-- about:end -->

## Development

To run migrations and load sample data:

```bash
python manage.py migrate
python manage.py loaddata server/fixtures/sample_data.json
```

Super User Dev Creds which gets created from sample_data:

email: developer@example.com |
password: password

To run the webserver, run the Django local server:

```bash
python manage.py runserver
```

The frontend is built using SolidJS. To run the development server with
hot-reloading, run the webpack dev server:

```bash
yarn run dev
```

Go to `http://localhost:8000` to start development. The Django server sets the
CSRF token cookie, and then redirects to the Webpack dev server for a better
developer experience (Hot module reloading) while working on the frontend.
