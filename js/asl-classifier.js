/**
 * ASL Alphabet Classifier
 * Classifies ASL fingerspelling letters from 21 MediaPipe hand landmarks.
 * Uses geometric features (angles, distances, finger states) for rule-based classification.
 * No external API needed — runs entirely on-device.
 */

const ASLClassifier = (() => {
  // Landmark indices
  const WRIST = 0;
  const THUMB = [1, 2, 3, 4];       // CMC, MCP, IP, TIP
  const INDEX = [5, 6, 7, 8];       // MCP, PIP, DIP, TIP
  const MIDDLE = [9, 10, 11, 12];
  const RING = [13, 14, 15, 16];
  const PINKY = [17, 18, 19, 20];
  const ALL_FINGERS = [THUMB, INDEX, MIDDLE, RING, PINKY];
  const TIPS = [4, 8, 12, 16, 20];
  const PIPS = [3, 6, 10, 14, 18];
  const MCPS = [2, 5, 9, 13, 17];

  // ASL letter data — descriptions, difficulty, tips, hand shape hints
  const LETTER_DATA = {
    A: {
      description: "Make a fist with your thumb resting on the side of your index finger.",
      fingers: "All fingers curled into palm. Thumb alongside the fist, pointing up.",
      difficulty: "easy",
      tip: "Think of making a regular fist, but keep your thumb on the side, not wrapped over your fingers.",
      emoji: "✊"
    },
    B: {
      description: "Hold all four fingers straight up and together, with thumb tucked across palm.",
      fingers: "All four fingers extended straight up. Thumb folded across the palm.",
      difficulty: "easy",
      tip: "Like a flat hand salute! Keep fingers together and straight.",
      emoji: "🖐️"
    },
    C: {
      description: "Curve your hand into a C shape, like holding a cup.",
      fingers: "All fingers and thumb curved to form a C shape. Open space between thumb and fingers.",
      difficulty: "easy",
      tip: "Pretend you're holding a can of soda!",
      emoji: "🤏"
    },
    D: {
      description: "Index finger points straight up, other fingers curl to touch thumb tip.",
      fingers: "Index finger extended up. Middle, ring, and pinky curl to touch the thumb tip, forming a circle.",
      difficulty: "medium",
      tip: "Your index finger is the tall part of the letter D!",
      emoji: "☝️"
    },
    E: {
      description: "Curl all fingers down, with fingertips touching the thumb.",
      fingers: "All fingers bent down at the knuckles. Tips of fingers rest against the thumb pad.",
      difficulty: "medium",
      tip: "Like you're trying to hold something tiny with all your fingertips.",
      emoji: "🤌"
    },
    F: {
      description: "Touch index finger tip to thumb tip, other three fingers spread up.",
      fingers: "Index finger and thumb form a circle. Middle, ring, and pinky extended and spread.",
      difficulty: "medium",
      tip: "It's like the OK sign but with three fingers spread out!",
      emoji: "👌"
    },
    G: {
      description: "Index finger and thumb point sideways, parallel to each other.",
      fingers: "Index finger and thumb extend forward/sideways. Other fingers curled in.",
      difficulty: "hard",
      tip: "Like a little duck beak pointing to the side!",
      emoji: "🫰"
    },
    H: {
      description: "Index and middle fingers extend sideways together, pointing horizontally.",
      fingers: "Index and middle fingers point sideways together. Other fingers curled. Thumb tucked.",
      difficulty: "hard",
      tip: "Like G, but add your middle finger too!",
      emoji: "🤞"
    },
    I: {
      description: "Make a fist with only your pinky finger extended straight up.",
      fingers: "Pinky finger up straight. All other fingers in a fist. Thumb across fingers.",
      difficulty: "easy",
      tip: "Just your little pinky pointing up to the sky!",
      emoji: "🤙"
    },
    J: {
      description: "Start with I (pinky up), then trace the letter J in the air with your pinky.",
      fingers: "Same as I but with a downward J-curve motion with the pinky.",
      difficulty: "hard",
      tip: "It's the letter I with a little J-hook motion. For camera practice, just hold the I position!",
      emoji: "🤙"
    },
    K: {
      description: "Index finger up, middle finger angled forward, thumb between them.",
      fingers: "Index finger points up. Middle finger angles forward. Thumb wedges between index and middle.",
      difficulty: "hard",
      tip: "Like a peace sign but with your thumb stuck between the fingers.",
      emoji: "✌️"
    },
    L: {
      description: "Make an L shape with your index finger pointing up and thumb pointing out.",
      fingers: "Index finger straight up. Thumb extends to the side at a right angle. Other fingers curled.",
      difficulty: "easy",
      tip: "It actually looks like the letter L!",
      emoji: "🤟"
    },
    M: {
      description: "Three fingers (index, middle, ring) drape over thumb, which is tucked under.",
      fingers: "Index, middle, and ring fingers over the thumb. Pinky and thumb tucked under.",
      difficulty: "hard",
      tip: "Think of it as 3 fingers over the thumb — M has 3 humps!",
      emoji: "✊"
    },
    N: {
      description: "Two fingers (index, middle) drape over thumb, which is tucked under.",
      fingers: "Index and middle fingers over the thumb. Ring and pinky fingers curled. Thumb tucked.",
      difficulty: "hard",
      tip: "Like M, but only 2 fingers over the thumb — N has 2 humps!",
      emoji: "✊"
    },
    O: {
      description: "All fingertips touch the thumb tip, forming an O shape.",
      fingers: "All fingers curve to touch the thumb, making a round O shape.",
      difficulty: "easy",
      tip: "Like you're saying 'okay' with all your fingers making a circle!",
      emoji: "👌"
    },
    P: {
      description: "Like K, but point the hand downward.",
      fingers: "Same handshape as K (index up, middle forward, thumb between) but wrist angles down.",
      difficulty: "hard",
      tip: "Make a K and then point your hand toward the ground!",
      emoji: "👇"
    },
    Q: {
      description: "Like G, but point the hand downward.",
      fingers: "Index finger and thumb extend down. Other fingers curled.",
      difficulty: "hard",
      tip: "Make a G and point your hand down. Like a little duck beak facing the floor!",
      emoji: "👇"
    },
    R: {
      description: "Cross your index and middle fingers, other fingers curled.",
      fingers: "Index and middle fingers crossed. Ring and pinky curled. Thumb across.",
      difficulty: "medium",
      tip: "Cross your fingers for good luck — that's the letter R!",
      emoji: "🤞"
    },
    S: {
      description: "Make a fist with your thumb wrapped across the front of your fingers.",
      fingers: "All fingers curled into a tight fist. Thumb wraps over the front of the fingers.",
      difficulty: "easy",
      tip: "A regular closed fist with thumb across the front!",
      emoji: "✊"
    },
    T: {
      description: "Make a fist with your thumb tucked between index and middle fingers.",
      fingers: "Fist with thumb poking between the index and middle fingers.",
      difficulty: "medium",
      tip: "Like S, but tuck your thumb between your first two fingers!",
      emoji: "✊"
    },
    U: {
      description: "Index and middle fingers point straight up together.",
      fingers: "Index and middle fingers extended up, held together. Ring and pinky curled. Thumb across.",
      difficulty: "easy",
      tip: "Like a peace sign but keep the two fingers together, not spread!",
      emoji: "✌️"
    },
    V: {
      description: "Index and middle fingers spread apart in a V shape.",
      fingers: "Index and middle fingers extended up and spread apart. Ring and pinky curled. Thumb tucked.",
      difficulty: "easy",
      tip: "The peace sign! ✌️ Two fingers spread apart.",
      emoji: "✌️"
    },
    W: {
      description: "Index, middle, and ring fingers spread apart pointing up.",
      fingers: "Index, middle, and ring fingers extended and spread. Pinky curled. Thumb tucked.",
      difficulty: "easy",
      tip: "Three fingers up and spread — like showing the number 3!",
      emoji: "🖖"
    },
    X: {
      description: "Index finger bent into a hook, other fingers in a fist.",
      fingers: "Index finger bent/hooked at the middle joint. Other fingers in a fist. Thumb across.",
      difficulty: "medium",
      tip: "Like you're making a tiny hook with your index finger!",
      emoji: "☝️"
    },
    Y: {
      description: "Thumb and pinky extended out, other three fingers curled.",
      fingers: "Thumb and pinky finger extended. Index, middle, and ring fingers curled.",
      difficulty: "easy",
      tip: "The 'hang loose' or 'shaka' sign! 🤙",
      emoji: "🤙"
    },
    Z: {
      description: "Index finger traces the letter Z in the air.",
      fingers: "Start with index finger pointing out. Trace a Z shape in the air.",
      difficulty: "hard",
      tip: "Like drawing the letter Z with your finger! For camera practice, just point your index finger.",
      emoji: "☝️"
    }
  };

  // ----- Utility functions -----

  function dist(a, b) {
    return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2);
  }

  function dist2d(a, b) {
    return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
  }

  function angle(a, b, c) {
    const ba = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
    const bc = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };
    const dot = ba.x * bc.x + ba.y * bc.y + ba.z * bc.z;
    const magBA = Math.sqrt(ba.x ** 2 + ba.y ** 2 + ba.z ** 2);
    const magBC = Math.sqrt(bc.x ** 2 + bc.y ** 2 + bc.z ** 2);
    if (magBA === 0 || magBC === 0) return 0;
    return Math.acos(Math.max(-1, Math.min(1, dot / (magBA * magBC))));
  }

  function normalize(landmarks) {
    const w = landmarks[WRIST];
    const translated = landmarks.map(p => ({
      x: p.x - w.x, y: p.y - w.y, z: (p.z || 0) - (w.z || 0)
    }));
    const refDist = dist(translated[0], translated[9]) || 1;
    return translated.map(p => ({
      x: p.x / refDist, y: p.y / refDist, z: p.z / refDist
    }));
  }

  // ----- Feature extraction -----

  function getFingerState(lm) {
    const state = {};

    // For each finger, check if it's extended
    // Thumb: compare tip to IP joint relative to MCP
    const thumbExtended = dist2d(lm[4], lm[9]) > dist2d(lm[3], lm[9]);
    state.thumbOut = thumbExtended;

    // Check if thumb tip is above (lower y) or below fingers
    state.thumbUp = lm[4].y < lm[3].y;

    // Other fingers: tip is above PIP (lower y = higher on screen)
    const fingers = [
      { name: 'index', tip: 8, pip: 6, mcp: 5, dip: 7 },
      { name: 'middle', tip: 12, pip: 10, mcp: 9, dip: 11 },
      { name: 'ring', tip: 16, pip: 14, mcp: 13, dip: 15 },
      { name: 'pinky', tip: 20, pip: 18, mcp: 17, dip: 19 }
    ];

    for (const f of fingers) {
      // Extended if tip is above (y is less than) PIP
      state[f.name + 'Up'] = lm[f.tip].y < lm[f.pip].y;
      // Curled if tip is below MCP
      state[f.name + 'Curled'] = lm[f.tip].y > lm[f.mcp].y;
      // Bent: tip is between PIP and MCP
      state[f.name + 'Bent'] = !state[f.name + 'Up'] && !state[f.name + 'Curled'];
      // Curl angle at PIP
      state[f.name + 'Angle'] = angle(lm[f.mcp], lm[f.pip], lm[f.dip]);
    }

    // Thumb to fingertip distances
    state.thumbToIndex = dist(lm[4], lm[8]);
    state.thumbToMiddle = dist(lm[4], lm[12]);
    state.thumbToRing = dist(lm[4], lm[16]);
    state.thumbToPinky = dist(lm[4], lm[20]);

    // Inter-finger tip distances
    state.indexToMiddle = dist(lm[8], lm[12]);
    state.middleToRing = dist(lm[12], lm[16]);
    state.ringToPinky = dist(lm[16], lm[20]);
    state.indexToPinky = dist(lm[8], lm[20]);
    state.indexToRing = dist(lm[8], lm[16]);

    // Palm reference distance (wrist to middle MCP)
    state.palmSize = dist(lm[0], lm[9]) || 1;

    // Finger tip to palm center (approximate)
    const palmCenter = {
      x: (lm[0].x + lm[5].x + lm[17].x) / 3,
      y: (lm[0].y + lm[5].y + lm[17].y) / 3,
      z: (lm[0].z + lm[5].z + lm[17].z) / 3
    };
    state.indexToPalm = dist(lm[8], palmCenter);
    state.middleToPalm = dist(lm[12], palmCenter);
    state.ringToPalm = dist(lm[16], palmCenter);
    state.pinkyToPalm = dist(lm[20], palmCenter);
    state.thumbToPalm = dist(lm[4], palmCenter);

    // Count extended fingers
    state.extCount = [
      state.indexUp, state.middleUp, state.ringUp, state.pinkyUp
    ].filter(Boolean).length;

    state.allCurled = state.indexCurled && state.middleCurled && state.ringCurled && state.pinkyCurled;

    // Hand orientation — is it pointing sideways?
    state.handPointingSide = Math.abs(lm[9].x - lm[0].x) > Math.abs(lm[9].y - lm[0].y);

    // Is hand pointing down?
    state.handPointingDown = lm[9].y > lm[0].y;

    return state;
  }

  // ----- Classifier -----

  function classify(rawLandmarks) {
    if (!rawLandmarks || rawLandmarks.length < 21) return null;

    const lm = normalize(rawLandmarks);
    const s = getFingerState(lm);
    const p = s.palmSize;

    const scores = {};
    const addScore = (letter, score, reason) => {
      if (!scores[letter]) scores[letter] = { total: 0, reasons: [] };
      scores[letter].total += score;
      scores[letter].reasons.push(reason);
    };

    // ===== FIST-BASED LETTERS: A, S, T, E, M, N =====
    if (s.allCurled || s.extCount === 0) {
      // All fingers down — it's a fist variant
      if (s.thumbOut && s.thumbUp) {
        addScore('A', 5, 'fist + thumb side up');
      }
      if (!s.thumbOut && !s.thumbUp) {
        addScore('S', 4, 'fist + thumb across front');
      }
      if (s.thumbToIndex < 0.4) {
        addScore('T', 3, 'thumb between index/middle');
      }
      if (!s.thumbOut) {
        addScore('E', 2, 'fingertips near thumb');
        addScore('M', 1.5, 'fist variant');
        addScore('N', 1.5, 'fist variant');
      }
      addScore('S', 2, 'general fist');
      addScore('A', 1.5, 'general fist');
    }

    // ===== A: Fist with thumb on side =====
    if (s.allCurled && s.thumbOut) {
      addScore('A', 4, 'thumb out side');
    }

    // ===== B: Four fingers up, together =====
    if (s.indexUp && s.middleUp && s.ringUp && s.pinkyUp) {
      const together = s.indexToMiddle < 0.5 && s.middleToRing < 0.5 && s.ringToPinky < 0.5;
      const spread = s.indexToMiddle > 0.5 || s.middleToRing > 0.5;
      if (together && !s.thumbOut) {
        addScore('B', 6, '4 fingers up together, thumb in');
      }
      if (spread && !s.thumbOut) {
        addScore('W', 2, '4 fingers spread');
      }
      if (s.thumbOut) {
        addScore('B', 2, '4 fingers up');
      }
    }

    // ===== C: Curved hand =====
    if (s.indexBent && s.middleBent && s.ringBent && s.pinkyBent && s.thumbOut) {
      addScore('C', 5, 'all fingers curved, thumb out');
    }
    if (!s.indexUp && !s.indexCurled && !s.middleUp && !s.middleCurled) {
      if (s.thumbOut && s.thumbToIndex > 0.3) {
        addScore('C', 3, 'open curve shape');
      }
    }

    // ===== D: Index up, others form circle with thumb =====
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.thumbToMiddle < 0.4) {
        addScore('D', 6, 'index up + others touch thumb');
      } else {
        addScore('D', 3, 'index up alone');
      }
    }

    // ===== E: Fingers curled, tips touch thumb =====
    if (s.allCurled && !s.thumbOut) {
      const tipsNearThumb = s.thumbToIndex < 0.5 && s.thumbToMiddle < 0.5;
      if (tipsNearThumb) {
        addScore('E', 5, 'curled tips touching thumb');
      }
    }

    // ===== F: Index-thumb circle, 3 fingers up =====
    if (s.middleUp && s.ringUp && s.pinkyUp && !s.indexUp) {
      if (s.thumbToIndex < 0.35) {
        addScore('F', 7, 'thumb-index circle + 3 up');
      }
    }
    if (s.middleUp && s.ringUp && s.pinkyUp && s.thumbToIndex < 0.4) {
      addScore('F', 4, '3 fingers up, thumb near index');
    }

    // ===== G: Index + thumb pointing sideways =====
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp && s.handPointingSide) {
      addScore('G', 5, 'index out sideways');
    }

    // ===== H: Index + middle pointing sideways =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp && s.handPointingSide) {
      addScore('H', 5, 'index+middle sideways');
    }

    // ===== I: Only pinky up =====
    if (s.pinkyUp && !s.indexUp && !s.middleUp && !s.ringUp) {
      addScore('I', 7, 'only pinky up');
      addScore('J', 4, 'pinky up (J base)');
    }

    // ===== J: Same as I (motion letter) =====

    // ===== K: Index up, middle forward, thumb between =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (!s.handPointingSide) {
        const spread = s.indexToMiddle > 0.4;
        if (spread && s.thumbOut) {
          addScore('K', 5, 'index+middle spread + thumb between');
        }
        if (!spread) {
          addScore('U', 4, 'index+middle together up');
        }
      }
    }

    // ===== L: Index up + thumb out at angle =====
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp && s.thumbOut) {
      if (!s.handPointingSide) {
        addScore('L', 6, 'index up + thumb out = L shape');
      }
    }

    // ===== M, N: Fist with fingers over thumb =====
    if (s.allCurled && !s.thumbOut) {
      // Hard to distinguish without very precise landmarks
      // M = 3 fingers over thumb, N = 2
      addScore('M', 2, 'fist with thumb under');
      addScore('N', 2, 'fist with thumb under');
    }

    // ===== O: All fingertips touch thumb =====
    if (!s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.thumbToIndex < 0.35 && s.thumbToMiddle < 0.5) {
        if (s.indexBent || s.middleBent) {
          addScore('O', 5, 'fingers curved to thumb');
        }
      }
    }

    // ===== P: Like K but pointing down =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.handPointingDown) {
        addScore('P', 5, 'K shape pointing down');
      }
    }

    // ===== Q: Like G but pointing down =====
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp && s.handPointingDown) {
      addScore('Q', 5, 'G shape pointing down');
    }

    // ===== R: Index + middle crossed =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.indexToMiddle < 0.2 && !s.handPointingSide) {
        addScore('R', 5, 'index+middle crossed/very close');
      }
    }

    // ===== S: Tight fist, thumb across =====
    // Already handled in fist section

    // ===== T: Thumb between index+middle in fist =====
    // Already handled in fist section

    // ===== U: Index + middle up together =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.indexToMiddle < 0.35 && !s.handPointingSide && !s.handPointingDown) {
        addScore('U', 5, 'index+middle together straight up');
      }
    }

    // ===== V: Index + middle spread =====
    if (s.indexUp && s.middleUp && !s.ringUp && !s.pinkyUp) {
      if (s.indexToMiddle > 0.35 && !s.handPointingSide && !s.handPointingDown) {
        addScore('V', 5, 'index+middle spread apart');
      }
    }

    // ===== W: Index + middle + ring up and spread =====
    if (s.indexUp && s.middleUp && s.ringUp && !s.pinkyUp) {
      addScore('W', 6, '3 fingers up (not pinky)');
    }

    // ===== X: Index hooked/bent =====
    if (s.indexBent && !s.indexUp && !s.indexCurled && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      addScore('X', 5, 'index hooked, others down');
    }
    if (!s.indexUp && s.indexAngle > 0.8 && s.indexAngle < 2.2 && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      addScore('X', 3, 'index partially bent');
    }

    // ===== Y: Thumb + pinky out =====
    if (s.pinkyUp && s.thumbOut && !s.indexUp && !s.middleUp && !s.ringUp) {
      addScore('Y', 7, 'thumb + pinky out');
    }

    // ===== Z: Index pointing out (motion letter) =====
    if (s.indexUp && !s.middleUp && !s.ringUp && !s.pinkyUp) {
      addScore('Z', 2, 'index pointing (Z base)');
    }

    // Find best match
    let best = null;
    let bestScore = 0;
    for (const [letter, data] of Object.entries(scores)) {
      if (data.total > bestScore) {
        bestScore = data.total;
        best = letter;
      }
    }

    // Require minimum confidence
    if (bestScore < 3) return null;

    // Calculate confidence as a percentage (rough)
    const confidence = Math.min(100, Math.round((bestScore / 7) * 100));

    return {
      letter: best,
      confidence,
      scores,
      fingerState: s
    };
  }

  // Stability filter — require consistent detection
  let recentResults = [];
  const STABILITY_FRAMES = 5;

  function classifyStable(landmarks) {
    const result = classify(landmarks);
    if (!result) {
      recentResults = [];
      return null;
    }

    recentResults.push(result.letter);
    if (recentResults.length > STABILITY_FRAMES) {
      recentResults.shift();
    }

    if (recentResults.length < 3) return null;

    // Check if majority of recent frames agree
    const counts = {};
    for (const l of recentResults) {
      counts[l] = (counts[l] || 0) + 1;
    }

    let stableLetter = null;
    let maxCount = 0;
    for (const [l, c] of Object.entries(counts)) {
      if (c > maxCount) {
        maxCount = c;
        stableLetter = l;
      }
    }

    // Need at least 60% agreement
    if (maxCount / recentResults.length >= 0.6) {
      return { letter: stableLetter, confidence: result.confidence };
    }

    return null;
  }

  function resetStability() {
    recentResults = [];
  }

  function getLetterData(letter) {
    return LETTER_DATA[letter.toUpperCase()] || null;
  }

  function getAllLetterData() {
    return LETTER_DATA;
  }

  return {
    classify,
    classifyStable,
    resetStability,
    getLetterData,
    getAllLetterData,
    LETTER_DATA
  };
})();
