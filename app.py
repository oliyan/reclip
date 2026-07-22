import os
import json
import logging
from flask import Flask, request, jsonify, render_template
import yt_dlp

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default directory if the user leaves the text input blank
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

def resolve_download_dir(user_path=None):
    """Returns user path if valid, otherwise creates and returns default."""
    if user_path and str(user_path).strip():
        # Expand '~' to the user's home directory path
        path = os.path.expanduser(str(user_path).strip())
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except Exception as e:
            logging.error(f"Could not create custom directory {path}: {e}")
            pass
            
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    return DEFAULT_DOWNLOAD_DIR

def update_ytdlp(ydl_opts):
    try:
        import sys
        import subprocess
        logging.info("Attempting to update yt-dlp...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
        logging.info("yt-dlp update check complete.")
    except Exception as e:
        logging.error(f"Failed to update yt-dlp: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def get_info():
    data = request.json
    urls = data.get('urls', [])
    
    if not urls:
         return jsonify({'error': 'No URLs provided'}), 400

    results = []
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                try:
                    # Detect YouTube playlists explicitly to handle 'list=' parameter correctly
                    if 'youtube.com' in url and 'list=' in url:
                        # For YouTube playlists, yt-dlp treats the whole playlist as one entry if extract_flat=True
                        info = ydl.extract_info(url, download=False)
                        if 'entries' in info:
                            # It's a playlist, return multiple entries
                            for entry in info['entries']:
                                results.append({
                                    'title': entry.get('title', 'Unknown Title'),
                                    'url': entry.get('url', url),
                                    'thumbnail': entry.get('thumbnail', None),
                                    'duration': entry.get('duration', None),
                                    'id': entry.get('id', None),
                                    'webpage_url': entry.get('url', url) # fallback
                                })
                        else:
                            # Not a playlist or fallback needed
                            results.append({
                                'title': info.get('title', 'Unknown Title'),
                                'url': url,
                                'thumbnail': info.get('thumbnail', None),
                                'duration': info.get('duration', None),
                                'id': info.get('id', None),
                                'webpage_url': url
                            })
                    else:
                        # Standard single video fetch
                        info = ydl.extract_info(url, download=False)
                        results.append({
                            'title': info.get('title', 'Unknown Title'),
                            'url': url,
                            'thumbnail': info.get('thumbnail', None),
                            'duration': info.get('duration', None),
                            'id': info.get('id', None),
                            'webpage_url': url
                        })
                except Exception as e:
                    logging.error(f"Error fetching info for {url}: {e}")
                    results.append({
                        'title': 'Error fetching info',
                        'url': url,
                        'error': str(e)
                    })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    resolution = data.get('resolution', 'best')
    custom_path = data.get('download_path', '')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    download_dir = resolve_download_dir(custom_path)
    output_template = os.path.join(download_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    if format_type == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else: # mp4
        if resolution == 'best':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            ydl_opts['format'] = f'bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}][ext=mp4]/best'
            
        # Ensure final output is mp4 if possible using ffmpeg
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return jsonify({'success': True, 'message': f'Downloaded to {download_dir}'})
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"yt-dlp Download Error: {str(e)}")
        # Optional auto-update if error indicates unsupported URL/extractor issue
        if "Unsupported URL" in str(e) or "ExtractorError" in str(e):
             logging.info("Attempting auto-update of yt-dlp due to error...")
             update_ytdlp(ydl_opts)
             # Note: You generally wouldn't retry the download here automatically 
             # because the process needs to restart to pick up the new yt-dlp package.
             return jsonify({'error': f'Download failed. Auto-updated yt-dlp in background. Please restart the app and try again. Error: {str(e)}'}), 500
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logging.error(f"General Download Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initial auto-update check on boot (optional, can be disabled if too slow)
    update_ytdlp(None)
    app.run(host='0.0.0.0', port=8899, debug=True)