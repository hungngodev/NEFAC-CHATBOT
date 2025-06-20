# RAG Search Application

A full-stack Retrieval Augmented Generation (RAG) application using Langchain, FAISS, FastAPI, React, and OpenAI models.

## Project Structure - NEEDS UPDATING

```
rag-project/
├── backend/
│   ├── venv/
│   ├── app.py
│   ├── requirements.txt
│   ├── .env
│   └── .env.template
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
├── .gitignore
└── README.md
```

## Setup Instructions

### Backend Setup

1. Make sure you have correct Python version - should be <3.13:

```bash

python --version or python<version> -- version
```

2. Create and activate virtual environment:

```bash

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies (Python version <3.13) :

```bash
pip install -r requirements.txt
```

4. Start the backend server:

```bash
cd backend
uvicorn app:app --reload
```

### Frontend Setup

1. Install dependencies: # UPDATE

```bash
cd frontend
npm install
```

## Development Guidelines

1. Always activate the virtual environment:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Never commit sensitive data or API keys
3. Update this README when adding new features or changing setup requirements

## Contributing

1. Pull new code

```bash
git fetch
git pull
```

2. Create a new branch

```bash
git checkout -b "new branch name"
```

3. Make your changes

```bash
git add <file name>
git commit -m "new commit message"
git push origin <branch name>
```

4. Test thoroughly
5. Make a branch merge request

## License

MIT

# Migration & Inspiration

This project is inspired by and migrated from the following repositories:

- [uynx/NEFAC-Chatbot](https://github.com/uynx/NEFAC-Chatbot)
- [DorianAtSchool/nefac](https://github.com/DorianAtSchool/nefac)

We have adapted, refactored, and extended the codebase to fit our current needs. Please refer to those repositories for earlier history and context.
