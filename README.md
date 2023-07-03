# hub

UPAI's membership and payment management portal

The discussions for building this app are [here](https://upai.zulipchat.com/).


## Development

To run the webserver, run the Django local server:

```bash
python manage.py runserver
```

The frontend is built using SolidJS. To run the development server with
hot-reloading, run the webpack dev server:

```bash
yarn run dev
```

Go to `http://localhost:8000` to start development.  The Django server sets the
CSRF token cookie, and then redirects to the Webpack dev server for a better
developer experience (Hot module reloading) while working on the frontend.
