# Meeting Organizer Agent - Frontend (Vite dev server)
# Build context: frontend/
#   docker build -f frontend/Dockerfile -t moa-frontend frontend/
FROM node:20-alpine

WORKDIR /app

# Install dependencies first so the layer is cached across source edits.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# The compose file mounts ./frontend over /app and restores /app/node_modules
# from the image via an anonymous volume, so installed packages survive edits.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
