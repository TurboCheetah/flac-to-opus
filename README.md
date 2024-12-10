# flac-to-opus

**Convert FLAC audio files to opus**

[![demo](https://asciinema.org/a/2xCSHSn2I1XkT7KmOFzFts2S2.svg)](https://asciinema.org/a/2xCSHSn2I1XkT7KmOFzFts2S2)

---

## **Features**

- **Batch Transcoding:** Convert multiple FLAC files at once, preserving the
  original directory structure.
- **Custom Bitrate:** Choose a desired bitrate (e.g., 192k, 256k) to balance
  between audio quality and file size.
- **Parallel Processing:** Speed up the conversion process by utilizing multiple
  CPU cores.
- **Dry-Run Mode:** Preview which files will be transcoded without making any
  changes.
- **Detailed Logging:** Keep track of all operations with comprehensive log
  files.
- **Progress Indicators:** Stay informed with real-time progress bars during the
  transcoding process.
- **Robust File Handling:** Supports filenames with spaces, special characters,
  and more.

---

## Installation

Install using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install .
```

## **Usage**

### **Basic Conversion**

Convert all FLAC files from a source directory to opus in the destination
directory with default settings:

```bash
flac-to-opus /path/to/source /path/to/destination
```

### **Specify Bitrate**

Choose a custom bitrate (e.g., 256k) for the OPUS files:

```bash
flac-to-opus -b 256k /path/to/source /path/to/destination
```

### **Set Number of Parallel Jobs**

Optimize conversion speed by specifying the number of parallel jobs (e.g., 4):

```bash
flac-to-opus -j 4 /path/to/source /path/to/destination
```

_If the `-j` option is omitted, the tool will automatically detect and use all
available CPU cores._

### **Enable Verbose Output**

Get real-time feedback in the terminal during the conversion process:

```bash
flac-to-opus -v /path/to/source /path/to/destination
```

### **Perform a Dry-Run**

See which files would be transcoded without actually performing the conversion:

```bash
flac-to-opus -d /path/to/source /path/to/destination
```

---

## **Dependencies**

- **Python 3.x**
- **[opusenc](https://github.com/xiph/opus-tools) :** Part of the `opus-tools`
  package, for transcoding to opus
- **[rich](https://github.com/Textualize/rich) :** Nice logging and progress bar

---
