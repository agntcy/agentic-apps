#!/bin/bash

# Ensure we are in the frontend directory
cd "$(dirname "$0")"

echo "Checking Flutter environment..."
if ! command -v flutter &> /dev/null; then
    echo "Flutter is not installed. Please install Flutter first."
    exit 1
fi

# Check if platform folders exist, if not, regenerate them
if [ ! -d "android" ] && [ ! -d "ios" ] && [ ! -d "web" ]; then
    echo "Platform folders missing. Regenerating project structure..."
    # Run flutter create but keep existing code
    flutter create . --platforms=web,macos,ios,android
fi

echo "Installing dependencies..."
flutter pub get

echo "Done. You can now run 'flutter run -d web-server' (or your preferred device)."
