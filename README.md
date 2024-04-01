# Apple Music Play History Converter

The Apple Music Play History Converter is a web-based tool that allows you to easily convert your Apple Music play history data into a format compatible with Last.fm and Universal Scrobbler. With this converter, you can analyze your music listening habits and import your data into various music tracking platforms.

# Play with the Hosted Version
Visit <a href="https://labs.ashrafali.net/historyconverter">https://labs.ashrafali.net/historyconverter</a> to try the hosted version.

## Features

- Supports multiple Apple Music CSV file types:
  - "Play Activity"
  - "Recently Played Tracks"
  - "Play History Daily Tracks"
- Converts Apple Music CSV files into a format compatible with Last.fm and Universal Scrobbler
- Performs automatic reverse-chronological timestamping based on track duration
- Utilizes the iTunes API to fetch missing artist information for more accurate data (optional)
- Provides a real-time tabular preview of the converted data
- Offers one-click copy to clipboard and download as CSV functionality
- Completely client-side processing - no data is sent to any server

## Technologies Used

- HTML
- CSS (Pico.css)
- JavaScript
- Papa Parse (JavaScript library for parsing CSV files)

## Usage

1. Request your full Apple Music listening history from [privacy.apple.com](https://privacy.apple.com/).
2. Extract the downloaded ZIP archive and locate the relevant CSV files.
3. Open the Apple Music Play History Converter in your web browser.
4. Select the Apple Music CSV file you want to convert.
5. Choose the appropriate file type (Play Activity, Recently Played Tracks, or Play History Daily Tracks).
6. Enable/disable iTunes API checking for the "Play Activity" file type (note: may cause browser stalling or failures).
7. Click the "Convert" button and wait for the conversion process to complete.

The converted data will be displayed in the "Output CSV" section, and a live tabular preview will be shown below. Any missing required data (artist or track) will be highlighted in bold red, and hovering over those cells will display a tooltip indicating that blank fields may prevent data import.

Please note that the tabular preview is limited to displaying the first 15 rows of the converted data. However, the complete converted data will be available in the output CSV.

## Contributing

Contributions to the Apple Music Play History Converter are welcome! If you have any ideas, suggestions, or bug reports, please open an issue or submit a pull request on the GitHub repository.

## Contact

If you have any questions or just want to say hi, feel free to reach out to me at hello@ashrafali.net. You can also find more of my work at [https://ashrafali.net](https://ashrafali.net).

Happy converting!

With optimism,
Ashraf