/**
 * Hand Detector Module
 * Uses MediaPipe Hands via TensorFlow.js hand-pose-detection for real-time
 * hand landmark detection. Runs entirely in the browser — no server needed.
 *
 * Optimized for iOS Safari / iPhone 16 Pro.
 */

const HandDetector = (() => {
  let detector = null;
  let isRunning = false;
  let animFrameId = null;
  let lastDetectionTime = 0;
  const MIN_INTERVAL = 80; // ~12fps to save battery on mobile
  let onResultCallback = null;
  let currentVideo = null;
  let currentCanvas = null;

  // Load TF.js and hand-pose-detection dynamically
  async function loadScripts() {
    const scripts = [
      'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-core@4.22.0/dist/tf-core.min.js',
      'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-converter@4.22.0/dist/tf-converter.min.js',
      'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-backend-webgl@4.22.0/dist/tf-backend-webgl.min.js',
      'https://cdn.jsdelivr.net/npm/@tensorflow-models/hand-pose-detection@2.0.1/dist/hand-pose-detection.min.js'
    ];

    for (const src of scripts) {
      if (document.querySelector(`script[src="${src}"]`)) continue;
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
  }

  async function init(progressCallback) {
    try {
      if (progressCallback) progressCallback(10, 'Loading AI libraries...');
      await loadScripts();

      if (progressCallback) progressCallback(40, 'Setting up AI engine...');
      await tf.setBackend('webgl');
      await tf.ready();

      if (progressCallback) progressCallback(60, 'Loading hand detection model...');

      const model = handPoseDetection.SupportedModels.MediaPipeHands;
      detector = await handPoseDetection.createDetector(model, {
        runtime: 'tfjs',
        modelType: 'lite', // lite for better mobile performance
        maxHands: 1
      });

      if (progressCallback) progressCallback(100, 'Ready!');
      return true;
    } catch (err) {
      console.error('Hand detector init failed:', err);
      if (progressCallback) progressCallback(-1, 'Error loading: ' + err.message);
      return false;
    }
  }

  async function startCamera(videoElement) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false
      });

      videoElement.srcObject = stream;
      await videoElement.play();

      // Wait for video to produce frames
      await new Promise(resolve => {
        if (videoElement.readyState >= 2) {
          resolve();
        } else {
          videoElement.onloadeddata = resolve;
        }
      });

      return true;
    } catch (err) {
      console.error('Camera access failed:', err);
      return false;
    }
  }

  function stopCamera(videoElement) {
    if (videoElement && videoElement.srcObject) {
      videoElement.srcObject.getTracks().forEach(t => t.stop());
      videoElement.srcObject = null;
    }
  }

  function startDetection(videoElement, canvasElement, callback) {
    if (!detector) {
      console.error('Detector not initialized');
      return;
    }

    currentVideo = videoElement;
    currentCanvas = canvasElement;
    onResultCallback = callback;
    isRunning = true;

    // Size canvas to match video
    const resizeCanvas = () => {
      if (canvasElement && videoElement.videoWidth) {
        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;
      }
    };
    resizeCanvas();
    videoElement.addEventListener('resize', resizeCanvas);

    const loop = async (timestamp) => {
      if (!isRunning) return;
      animFrameId = requestAnimationFrame(loop);

      if (timestamp - lastDetectionTime < MIN_INTERVAL) return;
      lastDetectionTime = timestamp;

      try {
        if (videoElement.readyState < 2) return;
        const hands = await detector.estimateHands(videoElement);

        if (canvasElement) {
          drawLandmarks(canvasElement, hands, videoElement.videoWidth, videoElement.videoHeight);
        }

        if (onResultCallback) {
          if (hands.length > 0) {
            // Use keypoints (2D) for drawing, keypoints3D if available for classification
            const landmarks = hands[0].keypoints3D || hands[0].keypoints;
            onResultCallback(landmarks, true);
          } else {
            onResultCallback(null, false);
          }
        }
      } catch (err) {
        // Ignore frame errors, keep going
      }
    };

    requestAnimationFrame(loop);
  }

  function stopDetection() {
    isRunning = false;
    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }
    onResultCallback = null;
  }

  function drawLandmarks(canvas, hands, vw, vh) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (hands.length === 0) return;

    const kp = hands[0].keypoints;
    const scaleX = canvas.width / vw;
    const scaleY = canvas.height / vh;

    // Connection lines
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],       // thumb
      [0, 5], [5, 6], [6, 7], [7, 8],       // index
      [0, 9], [9, 10], [10, 11], [11, 12],  // middle
      [0, 13], [13, 14], [14, 15], [15, 16],// ring
      [0, 17], [17, 18], [18, 19], [19, 20],// pinky
      [5, 9], [9, 13], [13, 17]             // palm
    ];

    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(102, 126, 234, 0.8)';

    for (const [i, j] of connections) {
      if (kp[i] && kp[j]) {
        ctx.beginPath();
        ctx.moveTo(kp[i].x * scaleX, kp[i].y * scaleY);
        ctx.lineTo(kp[j].x * scaleX, kp[j].y * scaleY);
        ctx.stroke();
      }
    }

    // Draw dots
    for (let i = 0; i < kp.length; i++) {
      const p = kp[i];
      if (!p) continue;
      const x = p.x * scaleX;
      const y = p.y * scaleY;

      // Fingertips get bigger dots
      const isTip = [4, 8, 12, 16, 20].includes(i);
      const radius = isTip ? 6 : 4;

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = isTip ? '#FF6B6B' : '#667eea';
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  // Handle visibility change (iOS kills camera in background)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && isRunning && currentVideo) {
      // Restart camera if it was killed
      if (!currentVideo.srcObject || currentVideo.srcObject.getTracks().every(t => t.readyState === 'ended')) {
        startCamera(currentVideo).then(() => {
          if (currentCanvas && onResultCallback) {
            // Detection loop should auto-resume via requestAnimationFrame
          }
        });
      }
    }
  });

  return {
    init,
    startCamera,
    stopCamera,
    startDetection,
    stopDetection,
    drawLandmarks
  };
})();
