/**
 * ASL Alphabet Classifier v3
 *
 * Two-layer classification:
 * 1. KNN classifier (learns from YOUR hands — most accurate)
 * 2. Rule-based fallback (uses joint angles — works without training)
 *
 * Key fix: Uses PIP/DIP JOINT ANGLES to detect finger extension,
 * not distance-from-wrist (which fails when palm faces camera).
 */

const ASLClassifier = (() => {
  // Landmark indices
  const WRIST = 0;
  const THUMB = [1, 2, 3, 4];
  const INDEX = [5, 6, 7, 8];
  const MIDDLE = [9, 10, 11, 12];
  const RING = [13, 14, 15, 16];
  const PINKY = [17, 18, 19, 20];
  const TIPS = [4, 8, 12, 16, 20];
  const MCPS = [2, 5, 9, 13, 17];

  // ASL letter data
  const LETTER_DATA = {
    A: { description: "Make a fist with your thumb resting on the side of your index finger.", fingers: "All fingers curled into palm. Thumb alongside the fist, pointing up.", difficulty: "easy", tip: "Think of making a regular fist, but keep your thumb on the side, not wrapped over your fingers." },
    B: { description: "Hold all four fingers straight up and together, with thumb tucked across palm.", fingers: "All four fingers extended straight up. Thumb folded across the palm.", difficulty: "easy", tip: "Like a flat hand salute! Keep fingers together and straight." },
    C: { description: "Curve your hand into a C shape, like holding a cup.", fingers: "All fingers and thumb curved to form a C shape. Open space between thumb and fingers.", difficulty: "easy", tip: "Pretend you're holding a can of soda!" },
    D: { description: "Index finger points straight up, other fingers curl to touch thumb tip.", fingers: "Index finger extended up. Middle, ring, and pinky curl to touch the thumb tip, forming a circle.", difficulty: "medium", tip: "Your index finger is the tall part of the letter D!" },
    E: { description: "Curl all fingers down, with fingertips touching the thumb.", fingers: "All fingers bent down at the knuckles. Tips of fingers rest against the thumb pad.", difficulty: "medium", tip: "Like you're trying to hold something tiny with all your fingertips." },
    F: { description: "Touch index finger tip to thumb tip, other three fingers spread up.", fingers: "Index finger and thumb form a circle. Middle, ring, and pinky extended and spread.", difficulty: "medium", tip: "It's like the OK sign but with three fingers spread out!" },
    G: { description: "Index finger and thumb point sideways, parallel to each other.", fingers: "Index finger and thumb extend forward/sideways. Other fingers curled in.", difficulty: "hard", tip: "Like a little duck beak pointing to the side!" },
    H: { description: "Index and middle fingers extend sideways together, pointing horizontally.", fingers: "Index and middle fingers point sideways together. Other fingers curled. Thumb tucked.", difficulty: "hard", tip: "Like G, but add your middle finger too!" },
    I: { description: "Make a fist with only your pinky finger extended straight up.", fingers: "Pinky finger up straight. All other fingers in a fist. Thumb across fingers.", difficulty: "easy", tip: "Just your little pinky pointing up to the sky!" },
    J: { description: "Start with I (pinky up), then trace the letter J in the air with your pinky.", fingers: "Same as I but with a downward J-curve motion with the pinky.", difficulty: "hard", tip: "It's the letter I with a little J-hook motion. For practice, just hold the I position!" },
    K: { description: "Index finger up, middle finger angled forward, thumb between them.", fingers: "Index finger points up. Middle finger angles forward. Thumb wedges between index and middle.", difficulty: "hard", tip: "Like a peace sign but with your thumb stuck between the fingers." },
    L: { description: "Make an L shape with your index finger pointing up and thumb pointing out.", fingers: "Index finger straight up. Thumb extends to the side at a right angle. Other fingers curled.", difficulty: "easy", tip: "It actually looks like the letter L!" },
    M: { description: "Three fingers (index, middle, ring) drape over thumb, which is tucked under.", fingers: "Index, middle, and ring fingers over the thumb. Pinky and thumb tucked under.", difficulty: "hard", tip: "Think of it as 3 fingers over the thumb — M has 3 humps!" },
    N: { description: "Two fingers (index, middle) drape over thumb, which is tucked under.", fingers: "Index and middle fingers over the thumb. Ring and pinky fingers curled. Thumb tucked.", difficulty: "hard", tip: "Like M, but only 2 fingers over the thumb — N has 2 humps!" },
    O: { description: "All fingertips touch the thumb tip, forming an O shape.", fingers: "All fingers curve to touch the thumb, making a round O shape.", difficulty: "easy", tip: "Like you're saying 'okay' with all your fingers making a circle!" },
    P: { description: "Like K, but point the hand downward.", fingers: "Same handshape as K but wrist angles down.", difficulty: "hard", tip: "Make a K and then point your hand toward the ground!" },
    Q: { description: "Like G, but point the hand downward.", fingers: "Index finger and thumb extend down. Other fingers curled.", difficulty: "hard", tip: "Make a G and point your hand down." },
    R: { description: "Cross your index and middle fingers, other fingers curled.", fingers: "Index and middle fingers crossed. Ring and pinky curled. Thumb across.", difficulty: "medium", tip: "Cross your fingers for good luck — that's the letter R!" },
    S: { description: "Make a fist with your thumb wrapped across the front of your fingers.", fingers: "All fingers curled into a tight fist. Thumb wraps over the front of the fingers.", difficulty: "easy", tip: "A regular closed fist with thumb across the front!" },
    T: { description: "Make a fist with your thumb tucked between index and middle fingers.", fingers: "Fist with thumb poking between the index and middle fingers.", difficulty: "medium", tip: "Like S, but tuck your thumb between your first two fingers!" },
    U: { description: "Index and middle fingers point straight up together.", fingers: "Index and middle fingers extended up, held together. Ring and pinky curled. Thumb across.", difficulty: "easy", tip: "Like a peace sign but keep the two fingers together, not spread!" },
    V: { description: "Index and middle fingers spread apart in a V shape.", fingers: "Index and middle fingers extended up and spread apart. Ring and pinky curled.", difficulty: "easy", tip: "The peace sign! Two fingers spread apart." },
    W: { description: "Index, middle, and ring fingers spread apart pointing up.", fingers: "Index, middle, and ring fingers extended and spread. Pinky curled. Thumb tucked.", difficulty: "easy", tip: "Three fingers up and spread — like showing the number 3!" },
    X: { description: "Index finger bent into a hook, other fingers in a fist.", fingers: "Index finger bent/hooked at the middle joint. Other fingers in a fist.", difficulty: "medium", tip: "Like you're making a tiny hook with your index finger!" },
    Y: { description: "Thumb and pinky extended out, other three fingers curled.", fingers: "Thumb and pinky finger extended. Index, middle, and ring fingers curled.", difficulty: "easy", tip: "The 'hang loose' or 'shaka' sign!" },
    Z: { description: "Index finger traces the letter Z in the air.", fingers: "Start with index finger pointing out. Trace a Z shape in the air.", difficulty: "hard", tip: "Like drawing the letter Z with your finger!" }
  };

  // ===== MATH UTILITIES =====

  function dist(a, b) {
    return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + ((a.z || 0) - (b.z || 0)) ** 2);
  }

  function angleDeg(a, b, c) {
    // Angle at point b, formed by segments b→a and b→c, in degrees
    const ba = { x: a.x - b.x, y: a.y - b.y, z: (a.z || 0) - (b.z || 0) };
    const bc = { x: c.x - b.x, y: c.y - b.y, z: (c.z || 0) - (b.z || 0) };
    const dot = ba.x * bc.x + ba.y * bc.y + ba.z * bc.z;
    const magBA = Math.sqrt(ba.x ** 2 + ba.y ** 2 + ba.z ** 2);
    const magBC = Math.sqrt(bc.x ** 2 + bc.y ** 2 + bc.z ** 2);
    if (magBA === 0 || magBC === 0) return 0;
    const cos = Math.max(-1, Math.min(1, dot / (magBA * magBC)));
    return Math.acos(cos) * (180 / Math.PI);
  }

  function normalize(landmarks) {
    const w = landmarks[WRIST];
    const translated = landmarks.map(p => ({
      x: p.x - w.x,
      y: p.y - w.y,
      z: (p.z || 0) - (w.z || 0)
    }));
    const refDist = dist(translated[0], translated[9]) || 1;
    return translated.map(p => ({
      x: p.x / refDist,
      y: p.y / refDist,
      z: p.z / refDist
    }));
  }

  // ===== FEATURE EXTRACTION (for KNN) =====
  // Extract a fixed-size numeric feature vector from normalized landmarks
  function extractFeatures(lm) {
    const features = [];

    // 1. All 21 normalized landmark positions (63 values)
    for (let i = 0; i < 21; i++) {
      features.push(lm[i].x, lm[i].y, lm[i].z);
    }

    // 2. Finger curl angles at PIP and DIP (10 values)
    const fingerJoints = [
      [5, 6, 7], [6, 7, 8],     // index PIP, DIP
      [9, 10, 11], [10, 11, 12], // middle
      [13, 14, 15], [14, 15, 16],// ring
      [17, 18, 19], [18, 19, 20] // pinky
    ];
    for (const [a, b, c] of fingerJoints) {
      features.push(angleDeg(lm[a], lm[b], lm[c]) / 180);
    }

    // 3. Thumb curl angles (2 values)
    features.push(angleDeg(lm[1], lm[2], lm[3]) / 180);
    features.push(angleDeg(lm[2], lm[3], lm[4]) / 180);

    // 4. Fingertip-to-thumb distances (4 values)
    for (const tip of [8, 12, 16, 20]) {
      features.push(dist(lm[4], lm[tip]));
    }

    // 5. Inter-fingertip distances (6 values)
    const tips = [8, 12, 16, 20];
    for (let i = 0; i < tips.length; i++) {
      for (let j = i + 1; j < tips.length; j++) {
        features.push(dist(lm[tips[i]], lm[tips[j]]));
      }
    }

    // 6. Fingertip to palm center (4 values)
    const palm = {
      x: (lm[0].x + lm[5].x + lm[9].x + lm[13].x + lm[17].x) / 5,
      y: (lm[0].y + lm[5].y + lm[9].y + lm[13].y + lm[17].y) / 5,
      z: (lm[0].z + lm[5].z + lm[9].z + lm[13].z + lm[17].z) / 5
    };
    for (const tip of [8, 12, 16, 20]) {
      features.push(dist(lm[tip], palm));
    }

    return features; // 63 + 10 + 2 + 4 + 6 + 4 = 89 features
  }

  // ===== FINGER STATE DETECTION (ANGLE-BASED) =====

  function getFingerState(lm) {
    const s = {};

    // PIP angle: angle at PIP joint (MCP→PIP→DIP)
    // Extended finger: PIP angle > 150° (nearly straight)
    // Curled finger: PIP angle < 90° (bent)
    // Bent: between 90° and 150°

    const EXTENDED_THRESH = 140;
    const CURLED_THRESH = 100;

    // Index finger
    s.indexPIP = angleDeg(lm[5], lm[6], lm[7]);
    s.indexDIP = angleDeg(lm[6], lm[7], lm[8]);
    s.indexUp = s.indexPIP > EXTENDED_THRESH;
    s.indexCurled = s.indexPIP < CURLED_THRESH;
    s.indexBent = !s.indexUp && !s.indexCurled;

    // Middle finger
    s.middlePIP = angleDeg(lm[9], lm[10], lm[11]);
    s.middleDIP = angleDeg(lm[10], lm[11], lm[12]);
    s.middleUp = s.middlePIP > EXTENDED_THRESH;
    s.middleCurled = s.middlePIP < CURLED_THRESH;
    s.middleBent = !s.middleUp && !s.middleCurled;

    // Ring finger
    s.ringPIP = angleDeg(lm[13], lm[14], lm[15]);
    s.ringDIP = angleDeg(lm[14], lm[15], lm[16]);
    s.ringUp = s.ringPIP > EXTENDED_THRESH;
    s.ringCurled = s.ringPIP < CURLED_THRESH;
    s.ringBent = !s.ringUp && !s.ringCurled;

    // Pinky finger
    s.pinkyPIP = angleDeg(lm[17], lm[18], lm[19]);
    s.pinkyDIP = angleDeg(lm[18], lm[19], lm[20]);
    s.pinkyUp = s.pinkyPIP > EXTENDED_THRESH;
    s.pinkyCurled = s.pinkyPIP < CURLED_THRESH;
    s.pinkyBent = !s.pinkyUp && !s.pinkyCurled;

    // Thumb: use angle at IP joint (MCP→IP→TIP) and distance from palm
    s.thumbIP = angleDeg(lm[2], lm[3], lm[4]);
    s.thumbMCP = angleDeg(lm[1], lm[2], lm[3]);
    // Thumb is "out" if tip is far from palm center
    const palmCenter = {
      x: (lm[0].x + lm[5].x + lm[9].x + lm[13].x + lm[17].x) / 5,
      y: (lm[0].y + lm[5].y + lm[9].y + lm[13].y + lm[17].y) / 5,
      z: (lm[0].z + lm[5].z + lm[9].z + lm[13].z + lm[17].z) / 5
    };
    s.thumbToPalm = dist(lm[4], palmCenter);
    s.thumbOut = s.thumbToPalm > 0.7;

    // Thumb to fingertip distances
    s.thumbToIndex = dist(lm[4], lm[8]);
    s.thumbToMiddle = dist(lm[4], lm[12]);
    s.thumbToRing = dist(lm[4], lm[16]);
    s.thumbToPinky = dist(lm[4], lm[20]);

    // Inter-finger tip distances
    s.indexToMiddle = dist(lm[8], lm[12]);
    s.middleToRing = dist(lm[12], lm[16]);
    s.ringToPinky = dist(lm[16], lm[20]);
    s.indexToPinky = dist(lm[8], lm[20]);

    // Counts
    s.extCount = [s.indexUp, s.middleUp, s.ringUp, s.pinkyUp].filter(Boolean).length;
    s.allCurled = s.indexCurled && s.middleCurled && s.ringCurled && s.pinkyCurled;

    // Hand orientation
    const dx = lm[9].x - lm[0].x;
    const dy = lm[9].y - lm[0].y;
    s.handPointingSide = Math.abs(dx) > Math.abs(dy) * 1.2;
    s.handPointingDown = dy > 0.3;

    // Palm size reference
    s.palmSize = dist(lm[0], lm[9]) || 1;

    return s;
  }

  // ===== RULE-BASED CLASSIFIER =====

  function classifyRules(lm) {
    const s = getFingerState(lm);
    const scores = {};
    const add = (letter, score) => {
      scores[letter] = (scores[letter] || 0) + score;
    };

    // B: 4 fingers extended
    if (s.extCount === 4) {
      const together = s.indexToMiddle < 0.5 && s.middleToRing < 0.5 && s.ringToPinky < 0.5;
      if (together) add('B', 8);
      else add('B', 4);
      // Could also be W with 3 up if pinky is borderline
    }

    // W: 3 fingers up (index, middle, ring), pinky down
    if (s.indexUp && s.middleUp && s.ringUp && !s.pinkyUp) {
      add('W', 7);
    }

    // V: index + middle up, spread
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && !s.handPointingSide && !s.handPointingDown) {
      if (s.indexToMiddle > 0.3) add('V', 7);
      else add('U', 5);
    }

    // U: index + middle up, together
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && !s.handPointingSide && !s.handPointingDown) {
      if (s.indexToMiddle <= 0.3) add('U', 7);
    }

    // K: index + middle up, spread, thumb out
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && !s.handPointingSide) {
      if (s.indexToMiddle > 0.3 && s.thumbOut) add('K', 6);
    }

    // R: index + middle up, very close (crossed)
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && !s.handPointingSide) {
      if (s.indexToMiddle < 0.15) add('R', 7);
    }

    // H: index + middle sideways
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && s.handPointingSide) {
      add('H', 7);
    }

    // P: index + middle, hand pointing down
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && s.handPointingDown) {
      add('P', 7);
    }

    // Single finger up patterns
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.handPointingSide) {
        add('G', 7); // index sideways
      } else if (s.handPointingDown) {
        add('Q', 7); // index down
      } else if (s.thumbOut && s.thumbToIndex > 0.5) {
        add('L', 8); // index up + thumb out = L
      } else if (s.thumbToMiddle < 0.4) {
        add('D', 7); // index up + others touch thumb
      } else {
        add('D', 4);
        add('L', 3);
      }
    }

    // I: only pinky up
    if (s.pinkyUp && !s.indexUp && !s.middleUp && !s.ringUp) {
      if (s.thumbOut) add('Y', 8);
      else {
        add('I', 8);
        add('J', 4);
      }
    }

    // Y: thumb + pinky out
    if (s.pinkyUp && s.thumbOut && !s.indexUp && !s.middleUp && !s.ringUp) {
      add('Y', 8);
    }

    // Fist variants (all curled)
    if (s.allCurled || s.extCount === 0) {
      if (s.thumbOut) {
        add('A', 7);
      } else {
        if (s.thumbToIndex < 0.3) {
          add('T', 6);
        } else if (s.thumbToIndex < 0.5 && s.thumbToMiddle < 0.5) {
          add('E', 5);
        } else {
          add('S', 6);
        }
        add('M', 1);
        add('N', 1);
      }
    }

    // F: middle+ring+pinky up, index curled, thumb touching index
    if (s.middleUp && s.ringUp && s.pinkyUp && !s.indexUp && s.thumbToIndex < 0.35) {
      add('F', 8);
    }

    // C: all fingers bent (not curled, not extended) + thumb out
    if (s.indexBent && s.middleBent && s.thumbOut) {
      add('C', 5);
    }

    // O: all fingers curved toward thumb
    if (!s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp && s.thumbToIndex < 0.35) {
      if (s.indexBent || s.middleBent) {
        add('O', 6);
      }
    }

    // X: index hooked/bent only
    if (s.indexBent && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      add('X', 5);
    }

    // Z: same as D/index-point base (motion letter)
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp && !s.handPointingSide) {
      add('Z', 2);
    }

    // Find best
    let best = null, bestScore = 0;
    for (const [letter, score] of Object.entries(scores)) {
      if (score > bestScore) { bestScore = score; best = letter; }
    }
    if (bestScore < 3) return null;
    return { letter: best, confidence: Math.min(100, Math.round(bestScore / 8 * 100)), method: 'rules' };
  }

  // ===== KNN CLASSIFIER (learns from user) =====

  let knnData = {}; // { letter: [ [features], [features], ... ] }
  const KNN_K = 5;
  const SAMPLES_PER_LETTER = 15;

  function loadKNN() {
    try {
      const saved = localStorage.getItem('asl_knn_data');
      if (saved) knnData = JSON.parse(saved);
    } catch (e) {}
  }

  function saveKNN() {
    try {
      localStorage.setItem('asl_knn_data', JSON.stringify(knnData));
    } catch (e) {}
  }

  function addKNNSample(letter, landmarks) {
    const lm = normalize(landmarks);
    const features = extractFeatures(lm);
    if (!knnData[letter]) knnData[letter] = [];
    knnData[letter].push(features);
    // Keep max samples per letter
    if (knnData[letter].length > SAMPLES_PER_LETTER) {
      knnData[letter].shift();
    }
    saveKNN();
  }

  function getKNNSampleCount(letter) {
    return (knnData[letter] || []).length;
  }

  function getTotalKNNSamples() {
    let total = 0;
    for (const samples of Object.values(knnData)) total += samples.length;
    return total;
  }

  function getTrainedLetters() {
    const letters = [];
    for (const [letter, samples] of Object.entries(knnData)) {
      if (samples.length >= 3) letters.push(letter);
    }
    return letters;
  }

  function clearKNN(letter) {
    if (letter) {
      delete knnData[letter];
    } else {
      knnData = {};
    }
    saveKNN();
  }

  function euclideanDist(a, b) {
    let sum = 0;
    for (let i = 0; i < a.length; i++) {
      const d = a[i] - b[i];
      sum += d * d;
    }
    return Math.sqrt(sum);
  }

  function classifyKNN(landmarks) {
    if (getTotalKNNSamples() < 3) return null;

    const lm = normalize(landmarks);
    const features = extractFeatures(lm);

    // Find K nearest neighbors across all letters
    const neighbors = [];
    for (const [letter, samples] of Object.entries(knnData)) {
      for (const sample of samples) {
        const d = euclideanDist(features, sample);
        neighbors.push({ letter, dist: d });
      }
    }

    if (neighbors.length === 0) return null;

    neighbors.sort((a, b) => a.dist - b.dist);
    const topK = neighbors.slice(0, Math.min(KNN_K, neighbors.length));

    // Vote
    const votes = {};
    for (const n of topK) {
      // Weight by inverse distance
      const weight = 1 / (n.dist + 0.001);
      votes[n.letter] = (votes[n.letter] || 0) + weight;
    }

    let best = null, bestWeight = 0;
    for (const [letter, weight] of Object.entries(votes)) {
      if (weight > bestWeight) { bestWeight = weight; best = letter; }
    }

    // Confidence based on how dominant the winner is
    const totalWeight = Object.values(votes).reduce((a, b) => a + b, 0);
    const confidence = Math.round((bestWeight / totalWeight) * 100);

    // Only return if reasonably confident and nearest neighbor isn't too far
    if (confidence < 40 || topK[0].dist > 3.0) return null;

    return { letter: best, confidence, method: 'knn', dist: topK[0].dist };
  }

  // ===== COMBINED CLASSIFIER =====

  function classify(rawLandmarks) {
    if (!rawLandmarks || rawLandmarks.length < 21) return null;

    const lm = normalize(rawLandmarks);

    // Try KNN first (if trained)
    const knnResult = classifyKNN(rawLandmarks);
    const ruleResult = classifyRules(lm);

    if (knnResult && knnResult.confidence >= 50) {
      // KNN is confident — use it
      return knnResult;
    }

    if (knnResult && ruleResult && knnResult.letter === ruleResult.letter) {
      // Both agree — high confidence
      return {
        letter: knnResult.letter,
        confidence: Math.max(knnResult.confidence, ruleResult.confidence),
        method: 'both'
      };
    }

    if (knnResult && ruleResult) {
      // They disagree — prefer KNN if it has reasonable confidence
      if (knnResult.confidence >= 40) return knnResult;
      return ruleResult;
    }

    return knnResult || ruleResult;
  }

  // ===== STABILITY FILTER =====
  let recentResults = [];
  const STABILITY_FRAMES = 3;

  function classifyStable(landmarks) {
    const result = classify(landmarks);
    if (!result) {
      if (recentResults.length > 0) recentResults.shift();
      return null;
    }

    recentResults.push(result.letter);
    if (recentResults.length > STABILITY_FRAMES) recentResults.shift();
    if (recentResults.length < 2) return null;

    const counts = {};
    for (const l of recentResults) counts[l] = (counts[l] || 0) + 1;

    let stableLetter = null, maxCount = 0;
    for (const [l, c] of Object.entries(counts)) {
      if (c > maxCount) { maxCount = c; stableLetter = l; }
    }

    if (maxCount >= 2) {
      return { letter: stableLetter, confidence: result.confidence, method: result.method };
    }
    return null;
  }

  function resetStability() { recentResults = []; }

  function getLetterData(letter) { return LETTER_DATA[letter.toUpperCase()] || null; }
  function getAllLetterData() { return LETTER_DATA; }

  // Load saved KNN data on startup
  loadKNN();

  return {
    classify,
    classifyStable,
    classifyRules,
    classifyKNN,
    resetStability,
    getLetterData,
    getAllLetterData,
    addKNNSample,
    getKNNSampleCount,
    getTotalKNNSamples,
    getTrainedLetters,
    clearKNN,
    extractFeatures,
    normalize,
    LETTER_DATA
  };
})();
