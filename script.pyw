import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit,
    QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon

class PinterestDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pinterest Downloader")
        self.setGeometry(300, 300, 600, 300)
        
        # Set window icons
        self.set_icons()
        
        # Dark Mode Style (Windows 11-like)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                padding: 8px;
                color: #ffffff;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0086f0;
            }
            QTextEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                font-family: Consolas;
            }
        """)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # URL Input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Pinterest URL here...")
        layout.addWidget(self.url_input)
        
        # Download Button (Dark Blue)
        self.download_btn = QPushButton("DOWNLOAD")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)
        
        # Progress Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        # Create download folder
        self.download_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Pinterest_downloads")
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    def set_icons(self):
        """Set window and message box icons from icon files."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try .png first, then .ico
        icon_paths = [
            os.path.join(script_dir, "icon.png"),
            os.path.join(script_dir, "icon.ico")
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.show_message("Error", "Please enter a Pinterest URL.")
            return
        
        # Validate Pinterest URL
        if not self.is_valid_pinterest_url(url):
            self.show_message("Error", "Please enter a valid Pinterest URL (e.g., https://www.pinterest.com/pin/...)")
            return
        
        self.download_btn.setEnabled(False)
        self.download_thread = DownloadThread(url, self.download_folder)
        self.download_thread.log_signal.connect(self.update_log)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def is_valid_pinterest_url(self, url):
        """Check if the URL is a valid Pinterest URL."""
        parsed = urlparse(url)
        return parsed.netloc.endswith('pinterest.com') and ('/pin/' in url or '/pin/' in parsed.path)

    def update_log(self, message):
        self.log_output.append(message)

    def on_download_finished(self):
        self.download_btn.setEnabled(True)
        self.show_message("Success", "All media downloaded successfully!")

    def show_message(self, title, message):
        msg = QMessageBox(self)  # Set parent to ensure icon inheritance
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Icon.Information)
        
        # Inherit main window icon
        if not self.windowIcon().isNull():
            msg.setWindowIcon(self.windowIcon())
        
        # Dark mode styling
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
            }
        """)
        msg.exec()

class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    
    def __init__(self, url, save_folder):
        super().__init__()
        self.url = url
        self.save_folder = save_folder
    
    def run(self):
        try:
            self.log_signal.emit(f"Accessing Pinterest URL: {self.url}")
            
            # Set headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.url, headers=headers)
            if response.status_code != 200:
                self.log_signal.emit("❌ Failed to retrieve the Pinterest page.")
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all media elements
            media_elements = []
            
            # 1. Find image elements
            img_tags = soup.find_all('img')
            for img in img_tags:
                img_url = img.get('src') or img.get('data-src')
                if img_url and any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    media_elements.append(('image', urljoin(self.url, img_url)))
            
            # 2. Find video elements
            video_tags = soup.find_all('video')
            for video in video_tags:
                video_url = video.get('src') or (video.find('source') and video.find('source').get('src'))
                if video_url and any(ext in video_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                    media_elements.append(('video', urljoin(self.url, video_url)))
            
            # 3. Find Pinterest's special video containers
            for div in soup.find_all('div', {'data-test-id': 'video-component'}):
                if div.get('data-video-src'):
                    media_elements.append(('video', urljoin(self.url, div.get('data-video-src'))))
            
            # 4. Find JSON data that might contain media URLs
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('contentUrl'):
                        url = data['contentUrl']
                        media_type = 'video' if any(ext in url.lower() for ext in ['.mp4', '.webm', '.mov']) else 'image'
                        media_elements.append((media_type, url))
                except:
                    pass
            
            # Remove duplicates
            unique_media = {}
            for media_type, url in media_elements:
                # Clean the URL by removing query parameters
                clean_url = url.split('?')[0]
                unique_media[clean_url] = (media_type, clean_url)
            
            media_list = list(unique_media.values())
            total_media = len(media_list)
            
            if not media_list:
                self.log_signal.emit("❌ No media found on this Pinterest page.")
                return
                
            self.log_signal.emit(f"Found {total_media} media items ({sum(1 for t, _ in media_list if t == 'image')} images, "
                                f"{sum(1 for t, _ in media_list if t == 'video')} videos). Starting download...")
            
            for i, (media_type, media_url) in enumerate(media_list):
                try:
                    # Get the file extension from the URL or default based on media type
                    parsed = urlparse(media_url)
                    filename = os.path.basename(parsed.path)
                    
                    if not filename or '.' not in filename:
                        ext = '.mp4' if media_type == 'video' else '.jpg'
                        filename = f"{media_type}_{i+1}{ext}"
                    else:
                        # Ensure the extension matches the media type
                        current_ext = os.path.splitext(filename)[1].lower()
                        if media_type == 'video' and current_ext not in ['.mp4', '.webm', '.mov']:
                            filename = f"{os.path.splitext(filename)[0]}.mp4"
                        elif media_type == 'image' and current_ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                            filename = f"{os.path.splitext(filename)[0]}.jpg"
                    
                    filepath = os.path.join(self.save_folder, filename)
                    
                    # Ensure unique filename
                    counter = 1
                    while os.path.exists(filepath):
                        name, ext = os.path.splitext(filename)
                        filepath = os.path.join(self.save_folder, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    # Download the media
                    with requests.get(media_url, headers=headers, stream=True) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    
                    self.log_signal.emit(f"✅ Downloaded {media_type}: {filename} ({i+1}/{total_media})")
                
                except Exception as e:
                    self.log_signal.emit(f"❌ Failed to download {media_url}: {str(e)}")
            
            self.log_signal.emit("🎉 All downloads completed!")
        
        except Exception as e:
            self.log_signal.emit(f"⚠️ Critical Error: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Force dark title bar
    
    # Set app-wide icon (for taskbar/dock)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_paths = [
        os.path.join(script_dir, "icon.png"),
        os.path.join(script_dir, "icon.ico")
    ]
    for path in icon_paths:
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            break
    
    window = PinterestDownloaderGUI()
    window.show()
    sys.exit(app.exec())