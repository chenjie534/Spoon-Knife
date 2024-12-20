import cv2
import os
import glob

files = glob.glob(os.path.join(r'D:\video_20241217\defect', '*.mp4'), recursive=True)
# Path to the video file
video_path = r'D:\video_20241217\output_2024-12-17_01-10-48.mp4'

# Output directory for the frames
output_dir = r'D:\video_20241217\test'
os.makedirs(output_dir, exist_ok=True)
# Frame counter
frame_count = 0
for video_path in files:
    # Open the video file
    cap = cv2.VideoCapture(video_path)

    # Read the video frame by frame
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Save the frame as a JPG file
        frame_filename = os.path.join(output_dir, f'frame_{frame_count:05d}.jpg')
        cv2.imwrite(frame_filename, frame)

        frame_count += 1

    # Release the video capture object
    cap.release()

    print(f'Total frames saved: {frame_count}' + video_path)
