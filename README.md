<<<<<<< HEAD
# SAFE SIGHT AI

SAFE SIGHT AI is a private-network PPE review workspace. It runs a reviewed
Ultralytics YOLO checkpoint against live cameras, recorded video, and still
images; associates required equipment with people; and retains incident
evidence in a local SQLite store.

## Included capabilities

- Validated image, video, and optional checkpoint uploads with size limits.
- Trusted-checkpoint policy: deployed instances disable browser model uploads
  and only load reviewed `.pt` weights from `models/` by default.
- Atomic evidence writes, SQLite WAL mode, bounded snapshot retention, and
  downloadable audit reports.
- Non-root Docker image, health check, secure Streamlit request protections,
  and a repeatable runtime/development dependency contract.

## Run locally

### 1. Native Desktop Application (PySide6)
Launch the desktop workspace with camera capture, timeline scrubbing, and evidence review:
```bash
python3 desktop.py
```

### 2. Browser Interface (Streamlit + WebRTC)
```bash
python3 -m streamlit run app.py
```

### Run Tests
```bash
python3 -m pytest tests/ -v
```

For a container deployment, copy a reviewed checkpoint to `models/best.pt`,
then run:

```bash
docker build -t safesight-ai .
docker run --rm -p 8501:8501 -v safesight-data:/app/data safesight-ai
```

For an internet-facing deployment, terminate TLS at a reverse proxy, set
Streamlit's `server.corsAllowedOrigins` and `server.allowedHosts` to your
approved domains, and restrict ingress to authenticated users. The application
is intentionally configured for same-origin browser access by default.

## Operating requirements

Treat model results as decision support, not a replacement for an on-site
safety officer. Before site rollout, validate precision and recall for each
camera angle, lighting condition, equipment policy, and workforce group; define
a human review process; set evidence-retention and access policies; and monitor
model drift.

The application defaults to a trusted model directory. To permit external
paths or browser checkpoint uploads during a controlled administration session,
set `PPE_ALLOW_EXTERNAL_MODEL_PATH=true` or `PPE_ENABLE_MODEL_UPLOAD=true`.
Never enable these settings for an internet-exposed operator instance.

## Commercial release checklist

You must obtain a commercial license for Ultralytics YOLO or otherwise comply
with its AGPL terms before selling a proprietary deployment. Also obtain rights
to the supplied model weights and training data, conduct a privacy impact
assessment for recorded worker imagery, and provide local legal review for the
jurisdictions where the product is deployed.
=======
# PPE-Vision

PPE Vision is a computer-vision project that uses a trained YOLO model to detect personal protective equipment (PPE) and PPE-related violation classes from a live camera or saved images.

The idea is simple: instead of making someone watch a safety camera all day, the application continuously looks at the video, identifies the classes that the trained model knows about, highlights the detections, and brings possible PPE violations to the user's attention.

This project was built as a practical application, not just as a model demo. It combines object detection, live video streaming, visual alerts, inspection reports, image analysis, and a dashboard-style interface in one Streamlit application.

Important: the application reports what the trained model actually detects. It does not invent PPE classes that are not present in final.pt, and an absence of a detected class should not be treated as proof that an item is physically absent unless the model was trained for that task.

1. What this project does

The application can be used in two main ways.
Live camera monitoring
A browser camera is streamed into the application through WebRTC. The YOLO model analyzes the incoming frames and draws the predictions directly on the video.

The dashboard can show:

detected PPE classes



violation classes



confidence scores



number of detected workers/objects where applicable



live FPS



current safety/inspection score



per-class detection counts



detailed per-object predictions



violation alerts



violation snapshots



a rolling detection-history chart



an event log for confirmed violation bursts



Saved-image inspection

You can also upload one image and run the same detector on it. The application returns the annotated image, individual predictions, confidence values, status, and bounding-box coordinates.

There is also a batch mode for analyzing multiple images and downloading the annotated results as a ZIP file.





2. Why the project is useful

In a real workplace, PPE monitoring can be repetitive. A person may need to check whether workers are wearing the equipment required for a particular area, but human monitoring is difficult to keep consistent for long periods.

PPE Vision is designed as a support tool for that workflow.

It can help with:





continuous visual monitoring



faster identification of potential PPE violations



reviewing saved inspection images



creating evidence snapshots



keeping a record of detected events



exporting results for later analysis

It is especially useful as a prototype for construction, manufacturing, laboratories, warehouses, workshops, and other environments where the trained model contains the appropriate PPE classes.





3. Main technologies







Technology



Purpose





Python



Main programming language





Streamlit



Dashboard and user interface





Ultralytics YOLO



Object detection / inference





OpenCV



Image processing and drawing detections





streamlit-webrtc



Browser camera streaming





PyAV



Video frame handling for WebRTC





NumPy



Numerical and image-array operations





Pandas



Detection tables and report generation

The application intentionally uses streamlit-webrtc rather than directly opening the machine's camera with cv2.VideoCapture(0). This makes the browser camera stream much more suitable for a Streamlit/WebRTC application.





4. Project structure

A simple project layout is enough:

PPE-Detection/
│
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── .venv/                 # Virtual environment (created locally)

The trained YOLO checkpoint is kept outside the project directory at the configured location:

/Users/universalimpex/Downloads/final.pt

The application is intentionally configured to use this exact path.





5. Model

The project uses a trained Ultralytics YOLO checkpoint named:

final.pt

The application loads it from:

/Users/universalimpex/Downloads/final.pt

The class names are read from the checkpoint itself. That means the application can work with the labels contained in the trained model instead of hard-coding a fixed list of PPE classes.

The application also uses label semantics to distinguish between commonly named compliance and violation classes. Examples of violation-style names include labels containing terms such as no-, without, missing, or violation.

The exact classes available in your project still depend entirely on how final.pt was trained.





6. How the prediction pipeline works

At a high level, the system follows this path:

Browser Camera / Uploaded Image
            ↓
       Frame / Image Decode
            ↓
        YOLO Inference
            ↓
  Confidence + IoU Filtering
            ↓
   Per-class Threshold Filtering
            ↓
   Class / Violation Analysis
            ↓
 ┌──────────┼──────────┐
 ↓          ↓          ↓
Overlay   Dashboard   Reports
 ↓          ↓          ↓
Video     Metrics    CSV / JSON

                    ↘
                 Violation
                 Snapshots

For live video, inference runs in the WebRTC processing path so that the Streamlit interface is not blocked by camera processing.

The application also protects shared live state with a lock because the video worker and Streamlit UI operate in different execution contexts.





7. Detection and prediction details

For each accepted detection, the application can keep information such as:





class label



display label



confidence score



violation/compliance interpretation



bounding-box coordinates



current class count

The live UI shows the result visually on the frame and also exposes a structured table under Detailed predictions.

A typical result conceptually looks like:

Class        Confidence     Status        X1   Y1   X2   Y2
-------------------------------------------------------------
Helmet          94.2%       COMPLIANT     ...  ...  ...  ...
No Vest         91.8%       VIOLATION     ...  ...  ...  ...
Person          97.1%       DETECTED      ...  ...  ...  ...

The exact labels will depend on the classes in final.pt.





8. Confidence thresholds

The sidebar provides a global confidence threshold and an IoU threshold.

Confidence

Confidence controls how certain the YOLO model must be before a detection is accepted.

Higher confidence:





usually reduces weak detections



can reduce false positives



can also remove difficult/low-confidence objects

Lower confidence:





can recover more difficult detections



can increase false positives

The application additionally supports per-class confidence thresholds, which is useful when some classes are easier to detect than others.

IoU / NMS threshold

The IoU threshold controls how aggressively overlapping detections are suppressed during non-maximum suppression.

The correct values depend on the model, scene, camera angle, and desired behaviour. There is no universal perfect threshold.





9. Live monitoring features



Live camera feed

Press START in the WebRTC camera component and allow browser camera access.

The live view can display:





bounding boxes



class names



confidence values



violation highlighting



a live safety HUD



current FPS



Violation alerts

When a violation-style class is detected, the dashboard can display an alert banner and optionally play a short browser audio alert.

The application includes event/burst handling so that a continuous violation is not treated as a brand-new event on every individual frame.

Violation snapshots

When automatic capture is enabled, violating frames can be saved in memory for the current session.

The gallery supports:





previewing snapshots



downloading individual images



downloading all snapshots as a ZIP



clearing the snapshot history





10. Inspection score

The dashboard includes a simple inspection/safety score.

This score is intentionally conservative. It is calculated from the PPE-like objects that are actually detected by the current model and active thresholds.

The score is not a replacement for a formal safety audit.

The dashboard uses three broad interpretations:





HIGH COMPLIANCE — high score



PARTIAL COMPLIANCE — middle range



ATTENTION REQUIRED — lower score

This is best understood as a visual indicator of what the detector is currently seeing, not as a legally or operationally definitive safety certification.





11. Saved-image inspection

Open Inspect a saved image and upload a JPG, JPEG, or PNG file.

The application runs the same YOLO detector and the same active thresholds used by the live system.

The output includes:





Annotated image



Per-object prediction table



Confidence values



Bounding-box coordinates



Violation count



A simple inspection interpretation



Download button for the annotated result

This is useful for testing the model without using the camera.





12. Batch image inspection

The Batch image inspection section allows multiple JPG/JPEG/PNG files to be analyzed in one run.

For each image, the application records information such as:





filename



analysis status



number of detections



number of violations



inspection score



detected classes

Annotated results are packaged into a ZIP file for download.

This is useful when you have a folder of inspection photographs and want to quickly review model behaviour across many images.





13. Reports and exports

The application can create downloadable reports from the current session.

CSV

The detections CSV is useful for opening the results in Excel, Google Sheets, Pandas, or another analysis tool.

JSON

The session JSON contains structured information such as:





report timestamp



model path



processed-frame count



current FPS



class counts



detailed detections



violation events



safety score



safety level



model interpretation note

Example report structure:

{
  "generated_at": "...",
  "model_path": "/Users/universalimpex/Downloads/final.pt",
  "total_processed_frames": 0,
  "current_fps": 0.0,
  "class_counts": {},
  "detections": [],
  "events": [],
  "safety_score": 100,
  "safety_level": "HIGH COMPLIANCE"
}





14. Alert event log

The application maintains a session event log for violation bursts.

This is different from the raw per-frame detections.

For example, if no-helmet remains visible for several frames, the system can treat that continuous condition as one event rather than generating a completely new event for every frame.

The event log can be reviewed directly from the dashboard and cleared when starting a new inspection session.





15. Runtime diagnostics

The advanced version includes runtime information intended to make troubleshooting easier.

The dashboard can expose information such as:





most recent inference error



inference error count



last update time



inference latency



peak detections



session uptime

This is particularly helpful when a model, device, camera, or dependency is behaving unexpectedly.

Errors are surfaced to the application instead of silently failing wherever practical, which makes debugging much easier than simply seeing an empty detection screen.





16. Hardware and inference device

The application can detect available inference devices such as:





CPU



CUDA GPU



Apple Metal / MPS when available

On an Apple Silicon Mac, MPS may be available depending on the installed PyTorch build.

For CPU systems, reducing image size and processing every second or third frame can make the application smoother.

For NVIDIA CUDA systems, GPU inference can provide much higher throughput.

The actual FPS will depend heavily on:





GPU/CPU



image size



model size



number of objects



camera resolution



browser/WebRTC behaviour



confidence/IoU settings





17. Installation on macOS

The following setup is recommended for the existing Mac environment.

Step 1 — open Terminal

cd ~/PPE-Detection



Step 2 — create the virtual environment

python3 -m venv .venv
source .venv/bin/activate



Step 3 — install dependencies

If requirements.txt is included with the project:

pip install -r requirements.txt

If you are rebuilding the environment manually, install the packages used by the application, including Streamlit, Ultralytics, OpenCV, NumPy, Pandas, PyAV, and streamlit-webrtc.

A NumPy 1.x-compatible environment is recommended for this project because compiled computer-vision/video packages may not be compatible with every NumPy 2.x combination.

For the previously encountered compatibility issue, using:

pip install "numpy<2"

is the safer choice.

Step 4 — check that the model exists

ls -lh /Users/universalimpex/Downloads/final.pt

You should see the final.pt file.

Step 5 — start Streamlit

streamlit run app.py

Then open the local Streamlit address shown in the terminal, normally:

http://localhost:8501





18. Starting the camera

Once the dashboard opens:





Make sure the model status says final.pt is loaded.



Choose the inference device.



Set the confidence and IoU thresholds.



Press START in the camera widget.



Allow the browser to access the camera.



Place a person/object in view.



Watch the bounding boxes and prediction metrics.

If nothing is detected, do not immediately assume the application is broken. Check the confidence threshold, model class names, lighting, camera angle, and whether the object is represented in the training data.





19. Troubleshooting



File does not exist: app.py

Make sure you are inside the correct project directory:

cd ~/PPE-Detection
ls

You should see app.py.

Then run:

streamlit run app.py



Model file not found

Check:

ls -lh /Users/universalimpex/Downloads/final.pt

If the file was moved or renamed, either restore it to that location or update MODEL_PATH in app.py.

ValueError: too many values to unpack

This can happen if two parts of the application use different versions of a function's return values. Make sure the complete app.py from the same project build is being used rather than mixing an older file with a newer one.

NumPy compatibility errors

If you see an error similar to:

A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x

use a NumPy 1.x release in the environment:

pip uninstall numpy -y
pip install "numpy<2"

Then restart Streamlit.

Camera does not start

Check that:





the browser has camera permission



no other application is exclusively using the camera



you are opening the application through localhost or a properly configured HTTPS deployment



the WebRTC component is loading successfully

For remote deployments, WebRTC may also require appropriate STUN/TURN configuration and network permissions.

Very low FPS

Try:

Inference size: 320 or 416
Process every Nth frame: 2 or 3

Also use a suitable GPU/MPS device when available.

Too many false detections

Increase the confidence threshold gradually.

You can also adjust the per-class sensitivity values rather than changing everything globally.

Real objects are missed

Lower the confidence threshold carefully and check whether the class is actually present in the trained model. A threshold change cannot make a model detect a class it was never trained to recognize.





20. Important limitation of the current model

The dashboard is only as capable as the trained final.pt checkpoint.

For example, if the model was trained to detect:

helmet
vest
no-helmet
no-vest
person

then the application can work with those classes.

But if the model was never trained to distinguish gloves, safety glasses, boots, or other equipment, the application cannot reliably create those predictions from the UI alone.

Likewise, a generic object detector does not automatically know that a helmet belongs to a particular person unless the model and/or additional logic was designed for that relationship.

That is why the application reports model-supported predictions instead of pretending it has information that the checkpoint does not contain.





21. Privacy and deployment note

The live camera feed is handled through the browser/WebRTC pipeline. Camera access is controlled by browser permissions.

This project is intended as a prototype/application for controlled environments. If it is deployed in a real workplace, the organization should separately address privacy, employee notification, data retention, access control, and local legal requirements.

The built-in snapshots and reports are session-oriented and should be treated as inspection evidence only when the surrounding operational process is appropriate.





22. How to demonstrate the project

A good project demonstration can be very simple.

Demo 1 — normal PPE

Show a worker wearing the PPE classes the model recognizes.

Point out:





bounding boxes



confidence scores



live metrics



inspection score



per-class breakdown



Demo 2 — violation

Show an image or live scene containing one of the trained violation classes.

Point out:





red violation box



alert banner



event entry



automatic snapshot



detailed prediction row



Demo 3 — saved image

Upload an image from the inspection section and show that the same trained model can analyze an image without the live camera.

Demo 4 — batch analysis

Upload several test images and download the annotated ZIP and CSV-style results.

This makes the project look like a complete application rather than only a YOLO demonstration.





23. Project objective

The main objective of PPE Vision is to build a practical computer-vision safety monitoring application that can:





detect PPE-related objects in real time



identify model-defined violation classes



display predictions clearly to a human operator



maintain lightweight inspection history



capture evidence images for violations



inspect individual or batches of saved images



export structured results for later review



remain understandable and usable without requiring the operator to understand the underlying ML model





24. Future improvements

The current application is already a complete working prototype, but there are several strong directions for a next version:





person-to-PPE association so each worker gets an individual compliance result



multi-camera monitoring



persistent database storage instead of session-only records



login and role-based access



configurable workplace PPE policies



email/SMS/WhatsApp-style alert integrations



automatic daily/weekly safety reports



heatmaps showing recurring violation areas



tracking the same worker across frames



improved temporal reasoning to reduce false positives



cloud deployment with secure WebRTC/TURN support



model version management and evaluation dashboards

These are extensions, not requirements for the current project.





25. Final note

PPE Vision was designed to feel like a small safety-monitoring product rather than a bare machine-learning experiment.

The important part is not just that YOLO draws a box around something. The application takes that prediction and turns it into something a person can actually use: a live view, a clear alert, an inspection result, evidence, history, and downloadable data.

At the same time, the project stays honest about what the model can and cannot know. The trained checkpoint remains the source of truth for the available classes and prediction capability.





Author / Project

Project: PPE Vision — Real-Time Workplace Safety Monitor
Core ML: Ultralytics YOLO
Application: Streamlit + WebRTC
>>>>>>> d8a8ebc9565757f8ac8e2bef392b0e69fc517b29
