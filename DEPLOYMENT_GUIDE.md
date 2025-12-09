# Deploying NEFAC Chatbot to a Remote Server

This guide explains how to deploy the application to another computer/server using Docker Hub images.

## Prerequisites
1.  **Docker Hub Account**: You need an account at [hub.docker.com](https://hub.docker.com/).
2.  **Docker & Docker Compose**: Installed on both machines.

---

## Step 1: Prepare Images (On Development Machine)

1.  Run the build script with your Docker Hub username:
    ```bash
    ./scripts/build_and_push.sh <your-docker-hub-username>
    ```
    *Example:* `./scripts/build_and_push.sh hungngodev`

    This script will:
    *   Ask you to log in to Docker Hub.
    *   Build the frontend and backend images.
    *   Push them to your Docker Hub repository.

---

## Step 2: Deploy (On Remote Machine)

1.  **Copy Files**: Copy the following files/folders to the remote server (e.g., into a `nefac-chat` folder):
    *   `docker/docker-compose.prod.yml`
    *   `.env` (Make sure production values are set!)
    *   `nginx.conf`

2.  **Run Application**:
    Navigate to the folder where you copied the files and run:

    ```bash
    # Export your username so docker-compose knows which images to pull
    export DOCKER_USERNAME=<your-docker-hub-username>

    # Pull the latest images
    docker-compose -f docker-compose.prod.yml pull

    # Start the application
    docker-compose -f docker-compose.prod.yml up -d
    ```

## Notes
*   **Environment Variables**: Ensure the `.env` file on the remote server has the correct production values (API keys, etc.).
*   **Ports**: The application will run on port `80` (Nginx) by default. Ensure your server's firewall allows traffic on port 80.
