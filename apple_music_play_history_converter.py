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

class CSVProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Music Play History Converter")
        self.root.minsize(width=800, height=600)  # Set the minimum width and height
        self.create_widgets()
        self.pause_itunes_search = False
        self.processing_thread = None
        self.file_size = 0
        self.row_count = 0
        
    def create_widgets(self):
        # Colors
        bg_color = '#ececed'
        primary_color = '#FF3B30'
        secondary_color = '#007AFF'
        text_color = '#000000'
        button_bg_color = '#51607a'
        button_text_color = '#FFFFFF'

        # Styles
        style = ttk.Style()
        style.configure('TLabel', background=bg_color, foreground=text_color)
        style.configure('TDefaultButton', background=button_bg_color, foreground=button_text_color)
        style.configure('TRedButton', background='#c53021', foreground='#FFFFFF')
        style.configure('TRadiobutton', background=bg_color, foreground=text_color)
        style.configure('TCheckbutton', background=bg_color, foreground=text_color)
        style.configure('TFrame', background=bg_color)

        self.root.configure(bg=bg_color)
        
        # Title and subtitle
        self.title_label = ttk.Label(self.root, text="Apple Music Play History Converter", font=("Arial", 24, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, pady=(20, 0))

        self.subtitle_label = ttk.Label(self.root, text="Convert Apple Music play history to a format ready to import to Last.fm.", font=("Arial", 14))
        self.subtitle_label.grid(row=1, column=0, columnspan=2, pady=(0, 20))

        self.info_label = ttk.Label(self.root, text="Everything happens in your computer. None of your data leaves the application.", font=("Arial", 12, "italic"), foreground=primary_color)
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
        self.play_history_radio = ttk.Radiobutton(self.file_frame, text="Play History Daily Tracks", variable=self.file_type_var, value="play-history")
        self.play_history_radio.grid(row=3, column=0, sticky='w', padx=(20, 0))

        self.recently_played_radio = ttk.Radiobutton(self.file_frame, text="Recently Played Tracks", variable=self.file_type_var, value="recently-played")
        self.recently_played_radio.grid(row=4, column=0, sticky='w', padx=(20, 0))

        self.play_activity_radio = ttk.Radiobutton(self.file_frame, text="Play Activity", variable=self.file_type_var, value="play-activity")
        self.play_activity_radio.grid(row=5, column=0, sticky='w', padx=(20, 0))

        # iTunes API search checkbox
        self.itunes_api_var = tk.BooleanVar()
        self.itunes_api_checkbox = ttk.Checkbutton(self.file_frame, text="Use iTunes API for Artist Search", variable=self.itunes_api_var)
        self.itunes_api_checkbox.grid(row=6, column=0, columnspan=3, sticky='w', padx=(20, 0))

        # Helper text
        self.helper_text = ttk.Label(self.file_frame, text="Select the appropriate file type based on your CSV file.", font=("Arial", 10, "italic"))
        self.helper_text.grid(row=7, column=0, columnspan=3, sticky='w', padx=(20, 0), pady=(5, 0))

        # Convert button
        self.convert_button = ttk.Button(self.file_frame, text="Convert", command=self.convert_csv, style='TButton')
        self.convert_button.grid(row=8, column=0, columnspan=3, pady=(20, 0))

        # Pause/Resume button
        self.pause_resume_button = ttk.Button(self.file_frame, text="Pause iTunes Search", command=self.toggle_pause_resume, style='TButton', state='disabled')
        self.pause_resume_button.grid(row=9, column=0, columnspan=3, pady=(10, 0))

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

    def check_file_size(self, file_path):
        self.file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        self.row_count = sum(1 for _ in open(file_path)) - 1  # Subtract 1 for header row
        size_info = f"File size: {self.file_size:.2f} MB, Rows: {self.row_count}"
        self.message_label.config(text=size_info, foreground="blue")

    def auto_select_file_type(self, file_path):
        file_name = file_path.split('/')[-1]
        if 'Play Activity' in file_name:
            self.file_type_var.set('play-activity')
        elif 'Recently Played Tracks' in file_name:
            self.file_type_var.set('recently-played')
        elif 'Play History Daily Tracks' in file_name:
            self.file_type_var.set('play-history')

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

        self.pause_resume_button.config(state='normal')
        self.processing_thread = threading.Thread(target=self.process_csv, args=(file_path, file_type))
        self.processing_thread.start()

    def toggle_pause_resume(self):
        if self.pause_itunes_search:
            self.pause_itunes_search = False
            self.pause_resume_button.config(text="Pause iTunes Search")
        else:
            self.pause_itunes_search = True
            self.pause_resume_button.config(text="Resume iTunes Search")

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
            chunk_number = 1
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
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
                    self.progress_label.config(text=f"Processing chunk {chunk_number}: Processed {processed_rows} out of {self.row_count} rows in {chunk_processing_time:.2f} seconds")
                    self.root.update_idletasks()
                    chunk_number += 1
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

        if file_type == 'play-history':
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

                    if not artist and self.itunes_api_var.get():
                        while self.pause_itunes_search:
                            time.sleep(0.1)  # Wait while paused
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
                except KeyError as e:
                    raise ValueError(f"Missing required column: {str(e)}")

        return processed_data, success_count, missing_artists, attributed_artists, failed_requests, itunes_search_time

    def search_artist(self, track, album):
        url = f"https://itunes.apple.com/search?term={track}+{album}&entity=song&limit=1"
        response = requests.get(url)
        data = response.json()

        if data['resultCount'] > 0:
            return data['results'][0]['artistName']
        else:
            raise Exception("Artist not found")

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

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Apple Music Play History Converter")
    app = CSVProcessorApp(root)
    root.mainloop()