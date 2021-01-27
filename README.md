# Notes Frontend

Webserver for hosting my personal notes on a Raspberry Pi.

## Getting Started

Create a new Conda environment (or install the required dependencies) from the requirements file:

```sh
conda install --yes --file requirements.txt
```

Update the notes submodule in `.gitmodules` to point at your [FOAM][foam-github] Git repo. Then run:

```sh
git submodule sync --recursive
```

Simply serve the Flask app normally:

```sh
python app.py
```

[foam-github]: https://github.com/foambubble/foam
