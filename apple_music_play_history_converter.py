import pandas as pd
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, scrolledtext
import sv_ttk
import requests
import threading
import time
import csv
import io
import os
from collections import deque
from threading import Lock

class CSVProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Music Play History Converter")
        self.root.minsize(width=800, height=600)  # Set the minimum width and height
        self.create_widgets()
        self.pause_itunes_search = False
        self.stop_itunes_search = False  # New flag for stopping search
        self.processing_thread = None
        self.file_size = 0
        self.row_count = 0
        
        # Rate limiting setup
        self.api_calls = deque(maxlen=20)  # Track last 20 API calls
        self.api_lock = Lock()  # Thread-safe lock for API calls
        self.rate_limit_timer = None
        self.api_wait_start = None

    def create_widgets(self):
        # Colors
        bg_color = '#ececed'
        primary_color = '#FF3B30'
        secondary_color = '#007AFF'
        text_color = '#000000'
        button_bg_color = '#51607a'
        button_text_color = '#000000'  # Changed to black

        # Styles
        style = ttk.Style()
        style.configure('TLabel', background=bg_color, foreground=text_color)
        style.configure('TButton', background=button_bg_color, foreground=button_text_color)
        
        # Configure red button style
        style.configure('Red.TButton', 
                       background='#c53021', 
                       foreground=button_text_color)  # Changed to black
        style.map('Red.TButton',
                 foreground=[('disabled', '#666666'),
                           ('pressed', button_text_color),
                           ('active', button_text_color)],
                 background=[('active', '#d64937'),
                           ('disabled', '#a52819')])

        style.configure('TRadiobutton', background=bg_color, foreground=text_color)
        style.configure('TCheckbutton', background=bg_color, foreground=text_color)
        style.configure('TFrame', background=bg_color)

        self.root.configure(bg=bg_color)
        
        # Title and subtitle
        self.title_label = ttk.Label(self.root, text="Apple Music Play History Converter", font=("Arial", 24, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, pady=(20, 0))

        self.subtitle_label = ttk.Label(self.root, text="Convert Apple Music play history to a format ready to import to Last.fm.", font=("Arial", 14))
        self.subtitle_label.grid(row=1, column=0, columnspan=2, pady=(0, 20))

        self.info_label = ttk.Label(self.root, text="Everything happens in your computer (except iTunes API Search). None of your data leaves the application.", font=("Arial", 12, "italic"), foreground=primary_color)
        self.info_label.grid(row=2, column=0, columnspan=2, pady=(0, 20))

        # Instructions button
        self.instructions_button = ttk.Button(self.root, text="Instructions", command=self.show_instructions, style='TButton')
        self.instructions_button.grid(row=3, column=0, columnspan=2, pady=(0, 20))

        # File selection
        self.file_frame = ttk.LabelFrame(self.root, text="Input CSV", padding=(20, 10))
        self.file_frame.grid(row=4, column=0, padx=20, pady=10, sticky='ew')

        self.file_label = ttk.Label(self.file_frame, text="Select Apple Music CSV:")
        self.file_label.grid(row=0, column=0, sticky='w', pady=(0, 5))

        self.file_entry = ttk.Entry(self.file_frame, width=50)
        self.file_entry.grid(row=1, column=0, columnspan=2, pady=(0, 5))

        self.browse_button = ttk.Button(self.file_frame, text="Choose File", command=self.browse_file, style='TButton')
        self.browse_button.grid(row=1, column=2, pady=(0, 5), padx=(5, 0))

        # File type selection
        self.file_type_label = ttk.Label(self.file_frame, text="Select File Type:")
        self.file_type_label.grid(row=2, column=0, sticky='w', pady=(10, 5))

        self.file_type_var = tk.StringVar()
        self.file_type_var.trace_add("write", lambda *args: self.update_time_estimate())
        
        self.play_history_radio = ttk.Radiobutton(self.file_frame, text="Play History Daily Tracks", variable=self.file_type_var, value="play-history")
        self.play_history_radio.grid(row=3, column=0, sticky='w', padx=(20, 0))

        self.recently_played_radio = ttk.Radiobutton(self.file_frame, text="Recently Played Tracks", variable=self.file_type_var, value="recently-played")
        self.recently_played_radio.grid(row=4, column=0, sticky='w', padx=(20, 0))

        self.play_activity_radio = ttk.Radiobutton(self.file_frame, text="Play Activity", variable=self.file_type_var, value="play-activity")
        self.play_activity_radio.grid(row=5, column=0, sticky='w', padx=(20, 0))

        self.converted_radio = ttk.Radiobutton(self.file_frame, text="Generic CSV (with Artist,Track,Album,Timestamp,Album Artist,Duration columns)", variable=self.file_type_var, value="generic")
        self.converted_radio.grid(row=6, column=0, sticky='w', padx=(20, 0))

        # iTunes API Frame
        self.itunes_frame = ttk.LabelFrame(self.file_frame, text="iTunes API Settings", padding=(10, 5))
        self.itunes_frame.grid(row=7, column=0, columnspan=3, sticky='ew', padx=(20, 0), pady=(10, 0))

        # iTunes API search checkbox
        self.itunes_api_var = tk.BooleanVar()
        self.itunes_api_checkbox = ttk.Checkbutton(self.itunes_frame, text="Use iTunes API for Artist Search", variable=self.itunes_api_var)
        self.itunes_api_checkbox.grid(row=0, column=0, sticky='w', pady=(0, 5))

        # Rate limit control
        self.rate_limit_frame = ttk.Frame(self.itunes_frame)
        self.rate_limit_frame.grid(row=1, column=0, sticky='w', pady=(0, 5))
        
        self.rate_limit_label = ttk.Label(self.rate_limit_frame, text="Rate limit (requests per minute):")
        self.rate_limit_label.grid(row=0, column=0, sticky='w', padx=(0, 5))
        
        self.rate_limit_var = tk.StringVar(value="20")
        self.rate_limit_entry = ttk.Entry(self.rate_limit_frame, textvariable=self.rate_limit_var, width=5)
        self.rate_limit_entry.grid(row=0, column=1, padx=(0, 10))
        
        # Rate limit warning
        self.rate_limit_warning = ttk.Label(self.rate_limit_frame, 
                                          text="Warning: Using more than 20 requests/min may result in API errors (403)", 
                                          foreground='red',
                                          font=("Arial", 10, "italic"))
        self.rate_limit_warning.grid(row=1, column=0, columnspan=2, sticky='w', pady=(2, 0))

        # Bind rate limit entry to update estimation
        self.rate_limit_entry.bind('<KeyRelease>', self.update_time_estimate)
        self.itunes_api_checkbox.config(command=self.update_time_estimate)

        # API Status frame
        self.api_status_frame = ttk.Frame(self.itunes_frame)
        self.api_status_frame.grid(row=2, column=0, sticky='w', pady=(0, 5))
        
        self.api_status_label = ttk.Label(self.api_status_frame, text="API Status: Ready")
        self.api_status_label.grid(row=0, column=0, sticky='w', padx=(0, 10))
        
        self.api_timer_label = ttk.Label(self.api_status_frame, text="Wait time: 0s")
        self.api_timer_label.grid(row=0, column=1, sticky='w')

        # API Control buttons frame
        self.api_control_frame = ttk.Frame(self.itunes_frame)
        self.api_control_frame.grid(row=3, column=0, sticky='w', pady=(0, 5))

        # Pause/Resume button
        self.pause_resume_button = ttk.Button(self.api_control_frame, text="Pause iTunes Search", command=self.toggle_pause_resume, style='TButton', state='disabled')
        self.pause_resume_button.grid(row=0, column=0, sticky='w', padx=(0, 5))

        # Stop button
        self.stop_button = ttk.Button(self.api_control_frame, 
                                    text="Stop iTunes Search", 
                                    command=self.stop_itunes_search, 
                                    style='Red.TButton', 
                                    state='disabled')
        self.stop_button.grid(row=0, column=1, sticky='w')

        # Helper text
        self.helper_text = ttk.Label(self.file_frame, text="Select the appropriate file type based on your CSV file.", font=("Arial", 10, "italic"))
        self.helper_text.grid(row=8, column=0, columnspan=3, sticky='w', padx=(20, 0), pady=(5, 0))

        # Convert button
        self.convert_button = ttk.Button(self.file_frame, text="Convert", command=self.convert_csv, style='TButton')
        self.convert_button.grid(row=9, column=0, columnspan=3, pady=(20, 0))

        # Output frame
        self.output_frame = ttk.LabelFrame(self.root, text="Output CSV", padding=(20, 10))
        self.output_frame.grid(row=4, column=1, padx=20, pady=10, sticky='ew')

        self.output_text = scrolledtext.ScrolledText(self.output_frame, height=15, width=80)
        self.output_text.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        self.copy_button = ttk.Button(self.output_frame, text="Copy to Clipboard", command=self.copy_to_clipboard, style='TButton')
        self.copy_button.grid(row=1, column=0, pady=(0, 10))

        self.save_button = ttk.Button(self.output_frame, text="Save as CSV", command=self.save_as_csv, style='TButton')
        self.save_button.grid(row=1, column=1, pady=(0, 10))

        # Data preview frame
        self.preview_frame = ttk.LabelFrame(self.root, text="Converted Data Preview", padding=(20, 10))
        self.preview_frame.grid(row=5, column=0, columnspan=2, padx=20, pady=10, sticky='ew')

        self.preview_table = ttk.Treeview(self.preview_frame, columns=("Artist", "Track", "Album", "Timestamp", "Album Artist", "Duration"), show='headings')
        self.preview_table.heading("Artist", text="Artist")
        self.preview_table.heading("Track", text="Track")
        self.preview_table.heading("Album", text="Album")
        self.preview_table.heading("Timestamp", text="Timestamp")
        self.preview_table.heading("Album Artist", text="Album Artist")
        self.preview_table.heading("Duration", text="Duration")
        self.preview_table.pack(fill='both', expand=True)

        # Progress bar
        self.progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=(20, 10))
        self.progress_frame.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky='ew')

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x', expand=True)

        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack()

        # Message label
        self.message_label = ttk.Label(self.root, text="", foreground=primary_color)
        self.message_label.grid(row=7, column=0, columnspan=2, padx=20, pady=10)

    def show_instructions(self):
        instructions = tk.Toplevel(self.root)
        instructions.title("Instructions")
        instructions.geometry("600x400")

        text = scrolledtext.ScrolledText(instructions, wrap=tk.WORD)
        text.pack(expand=True, fill='both')

        instructions_text = """

        Apple Music Play History Converter
        Convert Apple Music play history to a format that's ready to import to Last.fm. Currently compatible with Universal Scrobbler (https://universalscrobbler.com/).
        Everything happens in your browser. None of your data leaves the page.

        Request Your Full Listening History:

        1. Go to privacy.apple.com and sign in with your Apple ID.
        2. Request a copy of your data by selecting 'Apple Media Services' under the data categories.
        3. Wait for Apple to prepare your data and send you a link to download it.
        4. Extract the ZIP archive and look for the following files:
           - Apple Music - Play History Daily Tracks.csv
           - Apple Music - Recently Played Tracks.csv
           - Apple Music Play Activity.csv

        Using the Converter:

        1. Select the appropriate CSV file using the 'Choose File' button.
        2. Select the file type from the options provided.
        3. If using the Play Activity file, you can enable iTunes API checking to attempt to fill in missing artist information.
        4. Click 'Convert' to process the CSV file.
        5. View the preview of the converted data in the 'Converted Data Preview' section.
        6. Use the 'Copy to Clipboard' or 'Save as CSV' buttons to export the converted data.

        The tracks will be reverse timestamped based on their duration, ending with the current timestamp. If duration is not specified, a default track length of 3 minutes is assumed.

        Paste the output in the "Scrobble Manually in Bulk" section on Universal Scrobbler to scrobble your tracks.

        Made with ❤️ by Ashraf. Send 📧 hello@ashrafali.net.
        """
        text.insert(tk.END, instructions_text)
        text.configure(state='disabled')

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)
            self.auto_select_file_type(file_path)
            self.check_file_size(file_path)
            self.update_time_estimate()

    def check_file_size(self, file_path):
        self.file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        self.row_count = sum(1 for _ in open(file_path)) - 1  # Subtract 1 for header row
        size_info = f"File size: {self.file_size:.2f} MB, Rows: {self.row_count}"
        self.message_label.config(text=size_info, foreground="blue")

    def auto_select_file_type(self, file_path):
        file_name = os.path.basename(file_path)  # Get just the filename without path
        
        # Check for different possible file name patterns
        if any(x in file_name for x in ['Play Activity', 'Play Activity small']):
            self.file_type_var.set('play-activity')
        elif any(x in file_name for x in ['Recently Played Tracks', 'Apple Music - Recently Played Tracks']):
            self.file_type_var.set('recently-played')
        elif any(x in file_name for x in ['Play History Daily Tracks', 'Apple Music - Play History Daily Tracks']):
            self.file_type_var.set('play-history')
        else:
            # Try to detect if it's a generic CSV with the required columns
            try:
                df = pd.read_csv(file_path, nrows=1)
                required_columns = {'Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration'}
                if all(col in df.columns for col in required_columns):
                    self.file_type_var.set('generic')
                    self.message_label.config(text="Detected generic CSV format with required columns", foreground="blue")
            except Exception:
                pass

    def convert_csv(self):
        file_path = self.file_entry.get()
        file_type = self.file_type_var.get()
        if not file_path or not file_type:
            self.message_label.config(text="Please select a file and file type.", foreground="red")
            return

        if self.row_count > 5000:
            warning = f"Processing {self.row_count} rows may take longer than usual. Do you want to continue?"
            if not messagebox.askyesno("Warning", warning):
                return

        self.output_text.delete(1.0, tk.END)
        for row in self.preview_table.get_children():
            self.preview_table.delete(row)

        self.progress_var.set(0)
        self.progress_label.config(text="Processing...")
        self.message_label.config(text="")

        # Reset API search state
        self.stop_itunes_search = False
        self.pause_itunes_search = False
        if self.itunes_api_var.get():
            self.pause_resume_button.config(state='normal')
            self.stop_button.config(state='normal')

        self.processing_thread = threading.Thread(target=self.process_csv, args=(file_path, file_type))
        self.processing_thread.start()

    def toggle_pause_resume(self):
        if self.pause_itunes_search:
            self.pause_itunes_search = False
            self.pause_resume_button.config(text="Pause iTunes Search")
            self.api_status_label.config(text="API Status: Resumed")
        else:
            self.pause_itunes_search = True
            self.pause_resume_button.config(text="Resume iTunes Search")
            self.api_status_label.config(text="API Status: Paused")

    def stop_itunes_search(self):
        self.stop_itunes_search = True
        self.pause_itunes_search = False
        self.pause_resume_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.api_status_label.config(text="API Status: Stopped")
        self.api_timer_label.config(text="Wait time: 0s")
        self.api_wait_start = None  # Reset timer start
        self.wait_duration = 0  # Reset wait duration
        
        # Ask user if they want to continue with conversion
        if messagebox.askyesno("iTunes Search Stopped", 
                             "iTunes artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
            return True
        else:
            # If user doesn't want to continue, stop the entire process
            if self.processing_thread and self.processing_thread.is_alive():
                self.message_label.config(text="Conversion cancelled by user.", foreground="red")
                self.progress_label.config(text="Processing stopped.")
            return False

    def process_csv(self, file_path, file_type):
        chunk_size = 10000
        processed_data = []
        total_success_count = 0
        processed_rows = 0
        missing_artists = 0
        attributed_artists = 0
        failed_requests = 0

        start_time = time.time()
        itunes_search_time = 0

        try:
            # Configure pandas to handle mixed types properly
            chunk_iterator = pd.read_csv(
                file_path,
                chunksize=chunk_size,
                low_memory=False,
                dtype={
                    'Artist': str,
                    'Track': str,
                    'Album': str,
                    'Album Artist': str,
                    'Track Description': str,
                    'Container Description': str,
                    'Artist Name': str,
                    'Song Name': str,
                    'Album Name': str
                },
                na_values=['', 'nan', 'NaN', 'null', None],
                keep_default_na=True
            )

            chunk_number = 1
            for chunk in chunk_iterator:
                try:
                    chunk_start_time = time.time()
                    processed_chunk, success_count, missing_count, attributed_count, failed_count, chunk_itunes_time = self.process_chunk(chunk, file_type)
                    chunk_end_time = time.time()
                    
                    processed_data.extend(processed_chunk)
                    total_success_count += success_count
                    missing_artists += missing_count
                    attributed_artists += attributed_count
                    failed_requests += failed_count
                    itunes_search_time += chunk_itunes_time
                    processed_rows += len(chunk)
                    progress_percentage = (processed_rows / self.row_count) * 100
                    self.progress_var.set(progress_percentage)
                    
                    chunk_processing_time = chunk_end_time - chunk_start_time
                    self.progress_label.config(text=f"Processing chunk {chunk_number}: Processed {processed_rows:,} out of {self.row_count:,} rows in {chunk_processing_time:.2f} seconds")
                    self.root.update_idletasks()
                    chunk_number += 1
                except InterruptedError:
                    # Handle user cancellation
                    self.message_label.config(text="Conversion cancelled by user.", foreground="red")
                    self.progress_label.config(text="Processing stopped.")
                    return
                except Exception as e:
                    self.message_label.config(text=f"Error processing chunk {chunk_number}: {str(e)}", foreground="red")
                    return

            columns = ['Artist', 'Track', 'Album', 'Timestamp', 'Album Artist', 'Duration']
            self.processed_df = pd.DataFrame(processed_data, columns=columns)
            
            # Convert DataFrame to CSV string
            csv_buffer = io.StringIO()
            self.processed_df.to_csv(csv_buffer, index=False)
            csv_string = csv_buffer.getvalue()
            
            # Display CSV in output text box
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, csv_string)
            
            self.display_preview(self.processed_df.head(15))

            end_time = time.time()
            total_time = end_time - start_time

            message = f"CSV processing complete in {total_time:.2f} seconds."
            if self.itunes_api_var.get():
                message += f"\n{missing_artists} lines were missing artists. {attributed_artists} artists were found and attributed."
                message += f"\nTotal time spent on iTunes API searches: {itunes_search_time:.2f} seconds."
                if failed_requests > 0:
                    message += f"\n{failed_requests} iTunes API requests failed."
            else:
                message += f"\n{missing_artists} lines were missing artists."

            self.message_label.config(text=message, foreground="green")

        except pd.errors.EmptyDataError:
            self.message_label.config(text="The selected file is empty.", foreground="red")
        except pd.errors.ParserError:
            self.message_label.config(text="Error parsing the CSV file. Please check if it's a valid CSV.", foreground="red")
        except Exception as e:
            self.message_label.config(text=f"Error processing file: {str(e)}", foreground="red")

        self.progress_var.set(100)
        self.progress_label.config(text=f"Processing complete. Processed {total_success_count} out of {self.row_count} rows in {total_time:.2f} seconds.")
        self.pause_resume_button.config(state='disabled')

    def process_chunk(self, chunk, file_type):
        processed_data = []
        current_timestamp = pd.Timestamp.now()
        success_count = 0
        missing_artists = 0
        attributed_artists = 0
        failed_requests = 0
        itunes_search_time = 0

        if file_type in ['converted', 'generic']:
            # Handle both converted and generic CSV files
            for index, row in chunk.iterrows():
                try:
                    artist = row.get('Artist', '').strip() if pd.notna(row.get('Artist')) else ''
                    track = row.get('Track', '').strip() if pd.notna(row.get('Track')) else ''
                    album = row.get('Album', '').strip() if pd.notna(row.get('Album')) else ''
                    timestamp = row.get('Timestamp', current_timestamp)
                    album_artist = row.get('Album Artist', '').strip() if pd.notna(row.get('Album Artist')) else ''
                    
                    # Handle duration as either string or number
                    duration = row.get('Duration', 180)
                    if isinstance(duration, str):
                        try:
                            duration = int(float(duration))
                        except ValueError:
                            duration = 180
                    elif pd.isna(duration):
                        duration = 180
                    else:
                        duration = int(duration)

                    if not artist and self.itunes_api_var.get() and not self.stop_itunes_search:
                        while self.pause_itunes_search and not self.stop_itunes_search:
                            time.sleep(0.1)  # Wait while paused
                        
                        if self.stop_itunes_search:
                            # If search was stopped, check if we should continue
                            if not messagebox.askyesno("iTunes Search Stopped", 
                                                     "iTunes artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
                                raise InterruptedError("Conversion cancelled by user")
                            break  # Exit the loop and continue with remaining processing
                            
                        try:
                            itunes_start_time = time.time()
                            artist = self.search_artist(track, album)
                            itunes_end_time = time.time()
                            itunes_search_time += itunes_end_time - itunes_start_time
                            attributed_artists += 1
                            self.progress_label.config(text=f"iTunes API request {attributed_artists + failed_requests}: Artist found for '{track}'")
                            self.root.update_idletasks()
                        except Exception as e:
                            failed_requests += 1
                            self.progress_label.config(text=f"iTunes API request {attributed_artists + failed_requests}: Failed for '{track}' - {str(e)}")
                            self.root.update_idletasks()

                    if not artist:
                        missing_artists += 1

                    processed_data.append([artist, track, album, timestamp, artist or album_artist, duration])
                    success_count += 1
                except InterruptedError:
                    # Propagate the interruption
                    raise
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'play-history':
            for index, row in chunk.iterrows():
                try:
                    track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                    if len(track_info) == 2:
                        artist, track = track_info
                    else:
                        artist, track = '', row['Track Description']
                    artist = artist.strip()
                    track = track.strip()
                    duration = int(row['Play Duration Milliseconds']) // 1000 if pd.notna(row['Play Duration Milliseconds']) else 180
                    processed_data.append([artist, track, '', current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                    if not artist:
                        missing_artists += 1
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'recently-played':
            for index, row in chunk.iterrows():
                try:
                    track_info = row['Track Description'].split(' - ', 1) if pd.notna(row['Track Description']) else []
                    if len(track_info) == 2:
                        artist, track = track_info
                    else:
                        artist, track = '', row['Track Description']
                    artist = artist.strip()
                    track = track.strip()
                    album = row['Container Description'].strip() if pd.notna(row['Container Description']) else ''
                    duration = int(row['Media duration in millis']) // 1000 if pd.notna(row['Media duration in millis']) else 180
                    processed_data.append([artist, track, album, current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                    if not artist:
                        missing_artists += 1
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        elif file_type == 'play-activity':
            for index, row in chunk.iterrows():
                try:
                    artist = row.get('Artist Name', '').strip() if pd.notna(row.get('Artist Name')) else ''
                    track = row.get('Song Name', '').strip() if pd.notna(row.get('Song Name')) else ''
                    album = row.get('Album Name', '').strip() if pd.notna(row.get('Album Name')) else ''
                    duration = int(row.get('Media Duration In Milliseconds', 0)) // 1000 if pd.notna(row.get('Media Duration In Milliseconds')) else 180

                    if not artist and self.itunes_api_var.get() and not self.stop_itunes_search:
                        while self.pause_itunes_search and not self.stop_itunes_search:
                            time.sleep(0.1)  # Wait while paused
                        
                        if self.stop_itunes_search:
                            # If search was stopped, check if we should continue
                            if not messagebox.askyesno("iTunes Search Stopped", 
                                                     "iTunes artist search has been stopped. Do you want to continue with the conversion without searching for missing artists?"):
                                raise InterruptedError("Conversion cancelled by user")
                            break  # Exit the loop and continue with remaining processing
                            
                        try:
                            itunes_start_time = time.time()
                            artist = self.search_artist(track, album)
                            itunes_end_time = time.time()
                            itunes_search_time += itunes_end_time - itunes_start_time
                            attributed_artists += 1
                            self.progress_label.config(text=f"iTunes API request {attributed_artists + failed_requests}: Artist found for '{track}'")
                            self.root.update_idletasks()
                        except Exception as e:
                            failed_requests += 1
                            self.progress_label.config(text=f"iTunes API request {attributed_artists + failed_requests}: Failed for '{track}' - {str(e)}")
                            self.root.update_idletasks()

                    if not artist:
                        missing_artists += 1

                    processed_data.append([artist, track, album, current_timestamp, artist, duration])
                    current_timestamp -= pd.Timedelta(seconds=duration)
                    success_count += 1
                except InterruptedError:
                    # Propagate the interruption
                    raise
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        return processed_data, success_count, missing_artists, attributed_artists, failed_requests, itunes_search_time

    def update_rate_limit_timer(self):
        if self.api_wait_start is not None and not self.stop_itunes_search:  # Add stop check
            elapsed = time.time() - self.api_wait_start
            remaining = max(0, self.wait_duration - elapsed)
            self.api_timer_label.config(text=f"Wait time: {remaining:.1f}s")
            if remaining > 0 and not self.stop_itunes_search:  # Add stop check
                self.root.after(100, self.update_rate_limit_timer)
            else:
                self.api_wait_start = None
                if not self.stop_itunes_search:  # Only update to Ready if not stopped
                    self.api_status_label.config(text="API Status: Ready")
                self.api_timer_label.config(text="Wait time: 0s")

    def search_artist(self, track, album):
        # Rate limiting: ensure no more than X calls per minute
        with self.api_lock:
            current_time = time.time()
            rate_limit = int(self.rate_limit_var.get())
            
            # Remove API calls older than 1 minute
            while self.api_calls and current_time - self.api_calls[0] > 60:
                self.api_calls.popleft()
            
            # If we've made rate_limit calls in the last minute, wait
            if len(self.api_calls) >= rate_limit:
                self.wait_duration = 60 - (current_time - self.api_calls[0])
                if self.wait_duration > 0:
                    self.api_status_label.config(text="API Status: Rate Limited")
                    self.api_wait_start = current_time
                    self.update_rate_limit_timer()
                    time.sleep(self.wait_duration)
            
            try:
                # Clean the search terms
                track = track.split('(')[0].split('[')[0]  # Remove anything in parentheses or brackets
                track = track.replace('feat.', '').replace('ft.', '').strip()
                
                if not track:
                    raise Exception("No track name available")
                
                # Try first with just the track name
                artist = self._try_search(track)
                if not artist and album:
                    # If no result or artist not found, try with album
                    artist = self._try_search(f"{track} {album}")
                
                if artist:
                    self.api_status_label.config(text="API Status: Success")
                    return artist
                else:
                    raise Exception("No results found")
                    
            except Exception as e:
                self.api_status_label.config(text=f"API Status: Error - {str(e)}")
                raise

    def display_preview(self, df):
        for index, row in df.iterrows():
            self.preview_table.insert("", "end", values=list(row))

    def copy_to_clipboard(self):
        if self.row_count > 5000:
            warning = f"Copying {self.row_count} rows to clipboard may use a lot of memory. Do you want to continue?"
            if not messagebox.askyesno("Warning", warning):
                return

        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_text.get(1.0, tk.END))
        messagebox.showinfo("Copied", "CSV output copied to clipboard.")

    def save_as_csv(self):
        if not hasattr(self, 'processed_df'):
            messagebox.showerror("Error", "No data to save. Please process a CSV file first.")
            return

        file_type = self.file_type_var.get()
        if file_type == 'play-history':
            file_name = 'Play_History_Data.csv'
        elif file_type == 'recently-played':
            file_name = 'Recently_Played_Data.csv'
        else:
            file_name = 'Converted_Data.csv'

        file_path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=file_name, filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.processed_df.to_csv(file_path, index=False)
            messagebox.showinfo("Saved", f"Data saved to {file_path}")

    def _try_search(self, search_term):
        """Helper method to perform the actual iTunes API search."""
        try:
            # URL encode the search term
            encoded_term = requests.utils.quote(search_term)
            url = f"https://itunes.apple.com/search?term={encoded_term}&entity=song&limit=5"  # Get top 5 results
            
            # Make the API call with timeout
            response = requests.get(url, timeout=10)
            self.api_calls.append(time.time())  # Record the API call time
            
            if response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}")
            
            data = response.json()
            
            if not isinstance(data, dict) or 'resultCount' not in data or 'results' not in data:
                raise Exception("Invalid response format")
            
            if data['resultCount'] > 0:
                # Try to find the most relevant result
                # Prefer results where the track name matches exactly
                exact_matches = [r for r in data['results'] 
                               if r.get('trackName', '').lower().startswith(search_term.lower())]
                
                if exact_matches:
                    return exact_matches[0]['artistName']
                elif data['results']:
                    return data['results'][0]['artistName']
            
            return None
            
        except requests.exceptions.Timeout:
            raise Exception("Request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(str(e))

    def update_time_estimate(self, event=None):
        """Update the estimated time for API search based on rate limit and file size."""
        if not hasattr(self, 'row_count') or not self.row_count or not self.file_entry.get():
            return
            
        if not self.itunes_api_var.get():
            self.api_status_label.config(text="API Status: Ready")
            return
            
        try:
            rate_limit = int(self.rate_limit_var.get())
            if rate_limit <= 0:
                raise ValueError
                
            # Calculate estimated time
            missing_artists = self.count_missing_artists()
            if missing_artists == 0:
                self.api_status_label.config(text="No missing artists to search for")
                return
                
            total_minutes = missing_artists / rate_limit
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            seconds = int((total_minutes * 60) % 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
                
            # Show warning if rate limit > 20
            if rate_limit > 20:
                self.rate_limit_warning.config(foreground='red')
            else:
                self.rate_limit_warning.config(foreground='black')
                
            estimate_text = f"Estimated time for {missing_artists:,} missing artists: {time_str}"
            if rate_limit > 20:
                estimate_text += " (High rate limit may cause errors)"
                
            self.api_status_label.config(text=estimate_text)
            
        except ValueError:
            self.api_status_label.config(text="Please enter a valid rate limit")

    def count_missing_artists(self):
        """Count how many rows are missing artist information."""
        try:
            if not self.file_entry.get():
                return 0
                
            # Read CSV with proper settings to handle mixed types
            df = pd.read_csv(self.file_entry.get(), 
                           low_memory=False,
                           dtype=str,  # Read all columns as strings
                           na_values=['', 'nan', 'NaN', 'null', None],
                           keep_default_na=True)
            
            file_type = self.file_type_var.get()
            missing_count = 0
            
            # First check what columns we actually have
            columns = set(df.columns)
            
            if file_type == 'play-activity':
                # For play activity, check if we have a song but missing artist info
                if 'Song Name' in columns:
                    # Count rows where we have a song name but no artist info
                    has_song = df['Song Name'].notna() & (df['Song Name'].str.strip() != '')
                    # Check for artist info in Container Artist Name
                    has_artist = pd.Series(False, index=df.index)
                    if 'Container Artist Name' in columns:
                        has_artist |= df['Container Artist Name'].notna() & (df['Container Artist Name'].str.strip() != '')
                    missing_count = (has_song & ~has_artist).sum()
                    
            elif file_type in ['generic', 'converted']:
                if 'Artist' in columns:
                    missing_count = df['Artist'].isna().sum() + (df['Artist'].fillna('').str.strip() == '').sum()
            elif file_type in ['play-history', 'recently-played']:
                if 'Track Description' in columns:
                    missing_count = sum(1 for x in df['Track Description'].fillna('') if not str(x).strip() or ' - ' not in str(x))
            
            return missing_count
            
        except Exception as e:
            print(f"Error counting missing artists: {str(e)}")  # Debug info
            return 0

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Apple Music Play History Converter")
    app = CSVProcessorApp(root)
    root.mainloop()