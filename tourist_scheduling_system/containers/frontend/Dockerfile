# Stage 1: Build the Flutter web app
FROM ghcr.io/cirruslabs/flutter:stable AS build

WORKDIR /app

# Enable web support
RUN flutter config --enable-web

# Copy pubspec files first to cache dependencies
# Assuming build context is project root, so we copy from frontend/
COPY frontend/pubspec.yaml frontend/pubspec.lock ./
RUN flutter pub get

# Copy the rest of the application code
COPY frontend/ .

# Ensure web configuration is present (fixes "not configured for the web" error)
RUN flutter create . --platforms web

# Build the web application
RUN flutter build web --release

# Stage 2: Serve the app with Nginx
FROM nginx:alpine

# Install gettext for envsubst
RUN apk add --no-cache gettext

# Copy the build output from the previous stage
COPY --from=build /app/build/web /usr/share/nginx/html

# Copy custom Nginx configuration template
COPY containers/frontend/nginx.conf /etc/nginx/templates/default.conf.template

# Default backend URL (can be overridden at runtime)
# K8s service name: ui-dashboard-agent on port 80 (mapped to 10021)
ENV BACKEND_URL=http://ui-dashboard-agent

# Expose port 80
EXPOSE 80

# Start Nginx (envsubst is handled automatically by 20-envsubst-on-templates.sh in nginx:alpine)
CMD ["nginx", "-g", "daemon off;"]
