# CI/CD Workflow Setup

## Required GitHub Secrets

For the `build-and-push.yml` workflow to work, you need to set the following secrets in your GitHub repository:

1. Go to: **Settings → Secrets and variables → Actions**
2. Add the following secrets:

### `DOCKER_USERNAME`

- Value: `shishir01`
- Used for: Docker Hub authentication and image tagging

### `DOCKER_PASSWORD`

- Value: Your Docker Hub access token or password
- Used for: Docker Hub authentication

## How to Get Docker Hub Token

1. Go to https://hub.docker.com/
2. Sign in
3. Go to **Account Settings → Security**
4. Click **New Access Token**
5. Create a token with **Read & Write** permissions
6. Copy the token and add it as `DOCKER_PASSWORD` secret

## Workflow Details

The workflow builds and pushes 7 AI service images:

- `content_moderation`
- `image_tagger`
- `scene_recognition`
- `image_captioning`
- `face_recognition`
- `post_aggregator`
- `es_sync`

Each service is built in parallel using a matrix strategy.

## Image Naming

Images are pushed as:

- `shishir01/kaleidoscope-{service}:latest`
- `shishir01/kaleidoscope-{service}:{git-sha}`

## Troubleshooting

### Workflow Fails with "authentication required"

- Check that `DOCKER_USERNAME` and `DOCKER_PASSWORD` secrets are set
- Verify the Docker Hub token has correct permissions

### Workflow Fails with "Dockerfile not found"

- Ensure Dockerfile exists at `./services/{service}/Dockerfile`
- Check that the service name in matrix matches the directory name

### Build Fails

- Check the build logs for specific errors
- Verify all dependencies in `requirements.txt` are valid
- Ensure `shared/` directory exists in the repository
