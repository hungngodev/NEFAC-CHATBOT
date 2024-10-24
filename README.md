# RAG Search Application

A full-stack Retrieval Augmented Generation (RAG) application using React, TypeScript, Flask, and Claude.

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
1. Create and activate virtual environment:
```bash

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables: # NEEDS UPDATING
```bash
cp .env.template .env
# Edit .env with your actual API keys and configuration
```

4. Start the Flask server:
```bash
flask run
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
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
2. Never commit sensitive data or API keys
3. Update this README when adding new features or changing setup requirements

## Contributing
1. Create a new branch
2. Make your changes
3. Test thoroughly
4. Make a branch merge request

## License
MIT
