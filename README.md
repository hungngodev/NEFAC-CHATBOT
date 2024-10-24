# RAG Search Application

A full-stack Retrieval Augmented Generation (RAG) application using React, TypeScript, Flask, and Claude.

## Project Structure
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
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.template .env
# Edit .env with your actual API keys and configuration
```

4. Start the Flask server:
```bash
flask run
```

### Frontend Setup
1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm start
```

## Development Guidelines

1. Always activate the virtual environment before working on the backend:
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. After installing new Python packages:
```bash
pip freeze > requirements.txt
```

3. Never commit sensitive data or API keys
4. Keep the .env.template updated with any new environment variables
5. Update this README when adding new features or changing setup requirements

## Contributing
1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License
MIT