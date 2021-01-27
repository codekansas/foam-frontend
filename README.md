# Notes Frontend

Webserver for hosting my personal notes on a Raspberry Pi.

## Getting Started

Create a new Conda environment (or install the required dependencies) from the requirements file:

```sh
conda install --yes --file requirements.txt
```

Set `NOTES_ROOT` environment variable to point at your [FOAM][foam-github] notes root directory:

```sh
export NOTES_ROOT=/path/to/notes/root
```

Simply serve the Flask app normally:

```sh
flask run
```

[foam-github]: https://github.com/foambubble/foam
