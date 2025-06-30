# NEFAC Chatbot

A full-stack Retrieval Augmented Generation (RAG) application using Langchain, LangGraph, FastAPI, React, and OpenAI models, orchestrated with Docker.

## Project Structure

```
NEFAC_CHATBOT/
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── docker-compose.local.yml
├── backend/
│   ├── .pre-commit-config.yaml
│   ├── poetry.lock
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── src/
│       ├── app/
│       ├── core/
│       ├── config/
│       ├── schemas/
│       ├── service/
│       └── ...
├── frontend/
│   ├── ...
├── docs/
│   ├── ...
├── scripts/
│   ├── ...
└── .gitignore
```

## Setup Instructions

Refer to `docs/DEVELOPMENT.md` for detailed setup and development instructions.

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