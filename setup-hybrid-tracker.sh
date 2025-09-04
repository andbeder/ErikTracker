#!/bin/bash

# Setup script for Hybrid Erik Tracker
echo "🚀 Setting up Hybrid Erik Tracker..."

# Create required directories
echo "📁 Creating directories..."
mkdir -p erik_images
mkdir -p tracker_logs
mkdir -p frigate/config
mkdir -p frigate/media
mkdir -p double-take
mkdir -p homeassistant
mkdir -p mosquitto/config
mkdir -p mosquitto/data
mkdir -p mosquitto/log

# Set proper permissions
chmod 755 erik_images
chmod 755 tracker_logs
chmod 755 frigate/media

echo "✅ Directories created successfully"

# Create basic mosquitto config if it doesn't exist
if [ ! -f mosquitto/config/mosquitto.conf ]; then
    echo "📝 Creating mosquitto config..."
    cat > mosquitto/config/mosquitto.conf << EOF
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
EOF
    echo "✅ Mosquitto config created"
fi

# Copy Erik's images
echo "📸 Erik images setup:"
if [ -d "erik_images" ] && [ "$(ls -A erik_images)" ]; then
    echo "✅ Erik images folder contains $(ls erik_images | wc -l) files"
else
    echo "⚠️  Erik images folder is empty!"
    echo "   Please copy Erik's images to: $(pwd)/erik_images/"
    echo "   Supported formats: .jpg, .jpeg, .png, .bmp"
fi

# Create environment file template
if [ ! -f .env ]; then
    echo "📄 Creating .env template..."
    cat > .env << EOF
# Reolink Camera Credentials
RTSP_PASSWORD=your_camera_password_here

# CompreFace Configuration
registry=exadel/
POSTGRES_VERSION=1.5.0
ADMIN_VERSION=1.5.0
API_VERSION=1.5.0
FE_VERSION=1.5.0
CORE_VERSION=1.5.0

# Database Configuration
postgres_username=postgres
postgres_password=postgres
postgres_db=facedb

# Email Configuration (optional)
enable_email_server=false
email_host=smtp.gmail.com
email_username=
email_from=
email_password=

# Java Options
compreface_admin_java_options=-Xmx8g
compreface_api_java_options=-Xmx8g

# File Upload Limits
max_file_size=10MB
max_request_size=10MB

# Database Settings
save_images_to_db=true

# Performance Tuning
uwsgi_processes=2
uwsgi_threads=1
connection_timeout=10000
read_timeout=60000
EOF
    echo "✅ .env template created - please update with your settings"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🎯 Setup Summary:"
echo "  ✅ Directories created"
echo "  ✅ Basic configs created"
echo "  📸 Erik images: $(ls erik_images 2>/dev/null | wc -l) files"
echo ""
echo "📋 Next steps:"
echo "  1. Update .env file with your camera password and settings"
echo "  2. Add Erik's images to erik_images/ folder"
echo "  3. Build and start: docker compose up --build -d"
echo "  4. Monitor logs: docker compose logs -f hybrid-erik-tracker"
echo ""
echo "🔍 Test the hybrid tracker:"
echo "  - OSNet threshold: 0.484 (from your test results)"
echo "  - Face recognition: enabled with 0.75 threshold"
echo "  - Confidence fusion: 60% OSNet + 40% Face Recognition"
echo ""
echo "✅ Hybrid Erik Tracker setup complete!"