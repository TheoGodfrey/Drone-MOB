"""
MediaServer (Item 6)

Manages video streams from drones and re-broadcasts them to the GCS.
Simulates an RTSP client and pushes frames to the GcsServer.
"""
import asyncio
import cv2
import numpy as np
from typing import Dict
from coordinator.gcs_server import GcsServer

class MediaServer:
    """Handles RTSP/WebRTC streams from drones."""
    
    def __init__(self, gcs_server: GcsServer):
        self.gcs_server = gcs_server
        self.active_streams: Dict[str, asyncio.Task] = {}
        print("[MediaServer] Initialized.")
        
    async def run(self):
        """Main loop for the MediaServer (currently does nothing, is event-driven)."""
        print("[MediaServer] Running.")
        while True:
            # This loop could periodically check stream health
            await asyncio.sleep(60)
            
    async def start_stream(self, drone_id: str, rtsp_url: str):
        """Start pulling a video stream from a drone."""
        if drone_id in self.active_streams:
            print(f"[MediaServer] Stream for '{drone_id}' already running.")
            return
            
        print(f"[MediaServer] Starting stream for '{drone_id}' from {rtsp_url}...")
        
        # Create a task to process this stream
        task = asyncio.create_task(self._process_stream(drone_id, rtsp_url))
        self.active_streams[drone_id] = task
        
    async def stop_stream(self, drone_id: str):
        """Stop pulling a video stream from a drone."""
        if drone_id in self.active_streams:
            print(f"[MediaServer] Stopping stream for '{drone_id}'...")
            self.active_streams[drone_id].cancel()
            del self.active_streams[drone_id]
        
    async def _process_stream(self, drone_id: str, rtsp_url: str):
        """
        Background task to pull frames from a stream and send to GCS.
        (This simulates an RTSP client)
        """
        try:
            # In a real system:
            # cap = cv2.VideoCapture(rtsp_url)
            # if not cap.isOpened():
            #    print(f"[MediaServer] Error: Could not open stream {rtsp_url}")
            #    return
            
            # --- Simulation ---
            print(f"[MediaServer] (Sim) Connected to stream for '{drone_id}'")
            frame_num = 0
            while True:
                # ret, frame = cap.read()
                # if not ret:
                #    print(f"[MediaServer] Stream ended for '{drone_id}'")
                #    break
                
                # --- Create a simulated frame ---
                frame_num += 1
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    frame, f"DRONE {drone_id} - OVERWATCH",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                )
                cv2.putText(
                    frame, f"Frame: {frame_num}",
                    (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1
                )
                cv2.putText(
                    frame, f"RTSP: {rtsp_url}",
                    (20, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1
                )
                # --- End Simulation ---

                # Send the frame to the GCS for broadcast
                await self.gcs_server.broadcast_video_frame(frame)
                
                # Run at ~10 FPS
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            print(f"[MediaServer] Stream task for '{drone_id}' cancelled.")
        except Exception as e:
            print(f"[MediaServer] Error processing stream for '{drone_id}': {e}")
        finally:
            # cap.release()
            print(f"[MediaServer] (Sim) Disconnected from stream for '{drone_id}'")
            if drone_id in self.active_streams:
                del self.active_streams[drone_id]
