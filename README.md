# StegaVision

## Project Title
Image Steganography Using LSB and DCT

## Student
Kundrapu Tharun Kumar

## Enrollment
24CS003203

## Subject
Digital Image Processing

## Project Overview
StegaVision is an educational Flask application for embedding and recovering UTF-8 text in images with Least Significant Bit (LSB) and block Discrete Cosine Transform (DCT) methods. It also reports image information, pixel histograms, LSB planes, basic pixel statistics, and image-quality metrics.

## Problem Statement
Digital images can represent information in pixel values and frequency coefficients. This project demonstrates how those values can carry a message, how to recover it, and how embedding changes measurable image properties. It is a learning aid, not a replacement for encryption or a security product.

## Objectives
- Implement LSB steganography with an in-image signature and message length.
- Implement 8×8 block-DCT steganography using selected mid-frequency coefficients.
- Compare images with MSE, PSNR, and SSIM.
- Inspect image metadata, intensity histograms, and LSB planes.
- Demonstrate neutral, basic statistical steganalysis.

## Technologies
Python, Flask, OpenCV, NumPy, Pillow, SciPy, scikit-image, HTML, CSS, and vanilla JavaScript.

## Features
- Upload PNG, JPG/JPEG, BMP, and WEBP images (maximum request size: 16 MiB).
- Encode/decode UTF-8 text with the backend LSB and DCT implementations.
- Calculate payload capacity using each method's actual header and image dimensions.
- Download generated PNG stego images through a confined Flask route.
- View backend-generated metadata, 256-bin RGB/grayscale histograms, and an LSB-plane PNG.
- Compare two equal-sized images using MSE, PSNR, and SSIM.
- View actual LSB distribution, channel statistics, observations, and limitations.
- Drag/drop and browse uploads, local image previews, loading states, and copy-to-clipboard controls.

## Installation
From the project directory, create and activate a virtual environment.

Windows PowerShell:
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:
```sh
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

## Run
```sh
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000/). Flask creates `uploads/` and `outputs/` if they are absent. Uploaded source files are removed after each request; generated output PNGs remain in `outputs/` so their download links work. The Flask development server is for local demonstrations, not production deployment.

## LSB Method
The image is converted to RGB. A binary payload is formed as `STEGAV1`, a four-byte big-endian UTF-8 byte length, and the message bytes. Payload bits replace the least significant bit of RGB channel values in row-major order. The encoder writes PNG so the stored bits are not altered by lossy compression. Capacity reserves the complete 11-byte header.

## DCT Method
The image is converted to YCrCb and its luminance plane is processed in row-major 8×8 blocks. The encoder uses the mid-frequency coefficient pair `(2, 3)` and `(3, 2)`, not the DC coefficient `(0, 0)`. Differential modulation enforces a coefficient gap for each bit. The `DCTV1` header stores a four-byte big-endian message length and the original width/height. Images are padded to block boundaries and the generated PNG has the padded dimensions. Capacity is one bit per block after reserving the complete 17-byte header.

## Metrics
- MSE is the mean squared difference between corresponding pixel values; lower values mean less numerical difference.
- PSNR expresses that error in decibels relative to the 8-bit intensity range. Identical images yield positive infinity, serialized by the API as the string `Infinity`.
- SSIM compares local luminance, contrast, and structure; it is a similarity measure, not a security score.

For DCT output, metrics crop padded edge pixels only after validating the DCT signature, payload, and stored original dimensions. General image comparison rejects unrelated dimension mismatches.

## Image Analysis
The analysis API returns dimensions, mode, format, file size, and actual 256-bin channel histograms. Color images produce Red, Green, and Blue histograms; grayscale images produce a grayscale histogram. The LSB plane is calculated from actual source pixels, with bit 0 shown as black and bit 1 as white. `backend.image_analysis.create_difference_image()` creates an absolute RGB difference PNG for equal-size images; it is a Python utility, not a page/API control.

## Steganalysis
The educational analysis counts zero/one LSBs and reports per-channel mean, standard deviation, minimum, and maximum. Observations describe those statistics only. Statistical analysis alone cannot definitively determine whether an image contains hidden information.

## Project Structure
```text
StegaVision/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── backend/
│   ├── __init__.py
│   ├── lsb_steganography.py
│   ├── dct_steganography.py
│   ├── image_metrics.py
│   ├── image_analysis.py
│   └── steganalysis.py
├── templates/
│   ├── index.html
│   ├── lsb.html
│   ├── dct.html
│   ├── analysis.html
│   ├── steganalysis.html
│   └── about.html
├── static/
│   ├── css/style.css
│   └── js/
│       ├── main.js
│       ├── lsb.js
│       ├── dct.js
│       ├── analysis.js
│       └── steganalysis.js
├── uploads/
│   └── .gitkeep
├── outputs/
│   └── .gitkeep
├── docs/
└── tests/
    ├── __init__.py
    └── test_project.py
```

## Tests
The project uses Python's built-in `unittest` framework; no additional test package is required.

```sh
python -m unittest discover -s tests -v
python -m compileall app.py backend tests
```

## Limitations
- Steganography does not encrypt a message; use encryption separately when confidentiality is required.
- LSB data can be damaged by lossy recompression or image transformations.
- DCT uses a simple coefficient-pair modulation scheme. Its payload capacity is lower than LSB, and image transformations can still damage a payload.
- DCT output is padded to 8×8 block boundaries; the original dimensions are carried in its header, but the displayed/downloaded PNG retains the padded canvas dimensions.
- The basic statistical steganalysis is not a definitive detector.
- Generated PNGs remain in `outputs/` for their download URLs; remove old generated files manually when they are no longer needed.
