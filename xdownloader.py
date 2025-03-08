#!/usr/bin/env python
"""
X Video Downloader

A Tkinter-based GUI application to download videos from X (Twitter).
Author: svfuan
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import os
import threading
import time
import requests
import bs4
import re
from pathlib import Path
from queue import Queue, Empty

class XVideoDownloader:
    def __init__(self, master):
        self.master = master
        master.title("X Video Downloader")
        master.geometry("700x500")

        # Control flag for stopping downloads and a message queue for logging
        self.stop_flag = threading.Event()
        self.msg_queue = Queue()

        # Configure grid layout
        master.columnconfigure(0, weight=1)
        master.rowconfigure(2, weight=1)

        self._setup_ui()
        self._poll_queue()

    def _setup_ui(self):
        # Input frame for URLs
        input_frame = tk.Frame(self.master)
        input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        input_frame.columnconfigure(0, weight=1)

        lbl = tk.Label(input_frame,
                       text="Paste X Video URLs (one per line or comma-separated):\n(Format: https://x.com/i/status/XXXXXXX)",
                       font=("Arial", 10))
        lbl.grid(row=0, column=0, sticky="w")

        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD,
                                                     width=80, height=8, font=("Arial", 10))
        self.input_text.grid(row=1, column=0, pady=5, sticky="nsew")

        # Button frame for start and stop buttons
        btn_frame = tk.Frame(self.master)
        btn_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.start_btn = tk.Button(btn_frame, text="Download Videos",
                                   command=self.start_download,
                                   bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.start_btn.grid(row=0, column=0, padx=5, sticky="ew")

        self.stop_btn = tk.Button(btn_frame, text="Stop",
                                  command=self.stop_download,
                                  bg="#F44336", fg="white", font=("Arial", 10, "bold"))
        self.stop_btn.grid(row=0, column=1, padx=5, sticky="ew")

        # Output frame for log messages
        output_frame = tk.Frame(self.master)
        output_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD,
                                                      width=80, height=15, font=("Arial", 10))
        self.output_text.grid(row=0, column=0, sticky="nsew")

    def _poll_queue(self):
        """Check the message queue and update the log display."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.output_text.insert(tk.END, msg + "\n")
                self.output_text.see(tk.END)
        except Empty:
            pass
        self.master.after(100, self._poll_queue)

    def _log(self, message):
        """Add a message to the queue."""
        self.msg_queue.put(message)

    # --- Downloader functions (integrated) ---
    def _download_video(self, video_url, file_name):
        """
        Downloads the video from the given URL and saves it to the user's Downloads folder.
        """
        try:
            response = requests.get(video_url, stream=True)
            total_size = int(response.headers.get("content-length", 0))
            block_size = 1024
            downloaded = 0
            file_path = os.path.join(Path.home(), "Downloads", file_name)
            self._log(f"Downloading {file_name} ({total_size} bytes) to {file_path}...")
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(block_size):
                    if self.stop_flag.is_set():
                        self._log("Download halted by user.")
                        return False
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = downloaded / total_size * 100
                        self._log(f"Progress: {percent:.2f}%")
                        time.sleep(0.01)  # Allow UI updates
            self._log("Download completed successfully.")
            return True
        except Exception as e:
            self._log(f"Error during download: {e}")
            return False

    def _download_twitter_video(self, url):
        """
        Retrieves video details from the given URL and downloads the highest quality video.
        """
        api_url = f"https://twitsave.com/info?url={url}"
        self._log(f"Fetching video info from {api_url}")
        try:
            response = requests.get(api_url)
        except Exception as e:
            self._log(f"Failed to retrieve video info: {e}")
            return
        
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        try:
            download_section = soup.find_all("div", class_="origin-top-right")[0]
            quality_links = download_section.find_all("a")
            best_quality_url = quality_links[0].get("href")
        except Exception as e:
            self._log(f"Error extracting video URL: {e}")
            return
        
        try:
            title = soup.find_all("div", class_="leading-tight")[0]\
                        .find_all("p", class_="m-2")[0].text
            file_name = re.sub(r"[^a-zA-Z0-9]+", " ", title).strip() + ".mp4"
        except Exception as e:
            self._log(f"Error extracting title: {e}")
            file_name = "downloaded_video.mp4"
        
        self._log(f"Starting download for {file_name}")
        if not self._download_video(best_quality_url, file_name):
            self._log("Download was aborted or encountered an error.")

    # --- Download process ---
    def _process_downloads(self, urls):
        self.msg_queue.queue.clear()
        self._log("Initiating download process...")

        # Process URLs (supporting both newline and comma-separated)
        url_list = []
        for line in urls.splitlines():
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned and cleaned.startswith("https://x.com/i/status/"):
                    url_list.append(cleaned)
        
        if not url_list:
            self._log("No valid video URLs provided.")
            return
        
        for url in url_list:
            if self.stop_flag.is_set():
                self._log("Download process stopped by user.")
                break
            self._log(f"Processing: {url}")
            self._download_twitter_video(url)
            if self.stop_flag.is_set():
                break
            time.sleep(5)  # Pause between downloads
        
        self._log("Download process finished.")
        self.stop_flag.clear()

    def start_download(self):
        self.stop_flag.clear()
        urls = self.input_text.get("1.0", tk.END).strip()
        if not urls:
            messagebox.showwarning("Warning", "Please provide at least one URL.")
            return
        threading.Thread(target=self._process_downloads, args=(urls,), daemon=True).start()

    def stop_download(self):
        self.stop_flag.set()
        self._log("Stop requested by user.")

if __name__ == "__main__":
    root = tk.Tk()
    app = XVideoDownloader(root)
    root.mainloop()
