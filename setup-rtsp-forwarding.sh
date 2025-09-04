#!/bin/bash

# RTSP to HLS Forwarding Setup Script
# Maps IP addresses to port numbers (IP ending in 101 -> port 7101, etc.)

echo "🔧 Setting up RTSP to HLS forwarding for all cameras..."

# Camera configurations
CAMERAS=(
    "front_door:192.168.0.101:7101"
    "backyard:192.168.0.102:7102" 
    "side_yard:192.168.0.103:7103"
    "garage:192.168.0.104:7104"
)

# RTSP credentials
RTSP_USER="admin"
RTSP_PASS="hiver300"

# Create HLS output directory
mkdir -p /home/andrew/nvr/hls_streams

# Kill any existing FFmpeg processes
echo "🔪 Stopping existing FFmpeg processes..."
pkill -f "ffmpeg.*rtsp"

# Start FFmpeg for each camera
for camera_config in "${CAMERAS[@]}"; do
    IFS=':' read -r name ip port <<< "$camera_config"
    
    echo "📹 Setting up $name ($ip:$port)..."
    
    # RTSP input URL
    rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASS}@${ip}:554/h264Preview_01_main"
    
    # HLS output directory for this camera
    hls_dir="/home/andrew/nvr/hls_streams/$name"
    mkdir -p "$hls_dir"
    
    # Start FFmpeg in background to convert RTSP to HLS
    nohup ffmpeg -rtsp_transport tcp -i "$rtsp_url" \
        -c:v libx264 -preset ultrafast -tune zerolatency \
        -c:a aac -b:a 128k \
        -f hls -hls_time 2 -hls_list_size 5 -hls_flags delete_segments \
        -hls_segment_filename "$hls_dir/segment_%03d.ts" \
        "$hls_dir/playlist.m3u8" \
        > "/tmp/ffmpeg_${name}.log" 2>&1 &
    
    echo "✅ $name streaming to HLS on directory $hls_dir"
done

echo ""
echo "🎉 RTSP to HLS forwarding setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Forward these ports on your router:"
echo "   - Port 7101 -> $(hostname -I | awk '{print $1}'):7101 (Front Door)"
echo "   - Port 7102 -> $(hostname -I | awk '{print $1}'):7102 (Backyard)"
echo "   - Port 7103 -> $(hostname -I | awk '{print $1}'):7103 (Side Yard)"
echo "   - Port 7104 -> $(hostname -I | awk '{print $1}'):7104 (Garage)"
echo ""
echo "2. Set up HTTP server for HLS streams:"
echo "   sudo python3 -m http.server 8080 --directory /home/andrew/nvr/hls_streams"
echo ""
echo "🔍 Monitor FFmpeg processes with:"
echo "   ps aux | grep ffmpeg"
echo ""
echo "📊 Check logs with:"
echo "   tail -f /tmp/ffmpeg_*.log"