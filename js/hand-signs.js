/**
 * ASL Hand Sign SVG Illustrations
 * Each letter gets a unique SVG showing the correct hand position.
 * All SVGs are simple line drawings that clearly show finger positions.
 */

const HandSigns = (() => {

  // Reusable palm/wrist base
  const PALM = `<rect x="14" y="45" width="32" height="32" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  const PALM_R = `<rect x="14" y="45" width="32" height="32" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;

  // Helper: a finger going straight up from a base position
  function fingerUp(x, tipY, baseY) {
    return `<rect x="${x}" y="${tipY}" width="7" height="${baseY - tipY}" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  }

  // Helper: a curled finger (short stub)
  function fingerCurled(x, baseY) {
    return `<rect x="${x}" y="${baseY - 6}" width="7" height="10" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  }

  // Helper: thumb on side pointing up
  function thumbSide(y) {
    return `<rect x="5" y="${y}" width="7" height="18" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  }

  // Helper: thumb across front
  function thumbAcross(y) {
    return `<rect x="14" y="${y}" width="20" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  }

  // Helper: thumb out to side horizontally
  function thumbOut() {
    return `<rect x="1" y="52" width="15" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>`;
  }

  const signs = {
    // A: Fist with thumb on side
    A: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(16, 48)}
      ${fingerCurled(23, 46)}
      ${fingerCurled(30, 46)}
      ${fingerCurled(37, 48)}
      ${thumbSide(40)}
    </svg>`,

    // B: All four fingers up, thumb tucked
    B: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(16, 8, 48)}
      ${fingerUp(23, 4, 46)}
      ${fingerUp(30, 4, 46)}
      ${fingerUp(37, 8, 48)}
      ${thumbAcross(68)}
    </svg>`,

    // C: Curved hand like holding a cup
    C: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <path d="M38 20 Q48 22 48 35 Q48 50 42 60 Q38 68 30 72 Q22 68 18 60 Q12 50 12 38 Q12 30 18 25" fill="none" stroke="#A0785A" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M38 20 Q48 22 48 35 Q48 50 42 60 Q38 68 30 72 Q22 68 18 60 Q12 50 12 38 Q12 30 18 25" fill="#FFD5B8" opacity="0.4"/>
      <circle cx="38" cy="20" r="3" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <circle cx="18" cy="25" r="3" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
    </svg>`,

    // D: Index up, other fingers touch thumb forming circle
    D: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(22, 4, 46)}
      <ellipse cx="33" cy="42" rx="10" ry="8" fill="none" stroke="#A0785A" stroke-width="2" stroke-dasharray="4 2"/>
      ${fingerCurled(30, 46)}
      ${fingerCurled(37, 48)}
      <path d="M12 50 Q8 42 14 40" fill="none" stroke="#A0785A" stroke-width="2" stroke-linecap="round"/>
    </svg>`,

    // E: All fingers curled down, tips touch thumb
    E: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <path d="M18 48 Q18 36 22 38 Q24 40 22 48" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M24 46 Q24 34 28 36 Q30 38 28 46" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M30 46 Q30 34 34 36 Q36 38 34 46" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M36 48 Q36 36 40 38 Q42 40 40 48" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M10 55 Q7 48 12 44" fill="none" stroke="#A0785A" stroke-width="2" stroke-linecap="round"/>
    </svg>`,

    // F: Index-thumb circle, 3 fingers up and spread
    F: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <ellipse cx="16" cy="38" rx="7" ry="8" fill="none" stroke="#A0785A" stroke-width="2"/>
      ${fingerUp(23, 4, 46)}
      ${fingerUp(30, 4, 46)}
      ${fingerUp(37, 8, 48)}
    </svg>`,

    // G: Index + thumb pointing sideways
    G: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="30" width="32" height="28" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="42" y="33" width="16" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="42" y="48" width="14" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
    </svg>`,

    // H: Index + middle pointing sideways
    H: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="30" width="32" height="28" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="42" y="30" width="16" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="42" y="40" width="16" height="7" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
    </svg>`,

    // I: Pinky up only
    I: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(16, 48)}
      ${fingerCurled(23, 46)}
      ${fingerCurled(30, 46)}
      ${fingerUp(37, 10, 48)}
      ${thumbAcross(68)}
    </svg>`,

    // J: Like I but with motion arrow
    J: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(16, 48)}
      ${fingerCurled(23, 46)}
      ${fingerCurled(30, 46)}
      ${fingerUp(37, 10, 48)}
      ${thumbAcross(68)}
      <path d="M44 12 Q50 18 48 28 Q46 34 40 36" fill="none" stroke="#667eea" stroke-width="2" stroke-linecap="round" stroke-dasharray="3 2"/>
      <polygon points="38,34 43,38 40,32" fill="#667eea"/>
    </svg>`,

    // K: Index up, middle angled, thumb between
    K: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(18, 6, 48)}
      <rect x="28" y="12" width="7" height="34" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(15 31 46)"/>
      ${fingerCurled(35, 48)}
      ${fingerCurled(40, 50)}
      <path d="M12 48 L20 36" fill="none" stroke="#A0785A" stroke-width="2.5" stroke-linecap="round"/>
    </svg>`,

    // L: Index up + thumb out = L shape
    L: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(22, 4, 46)}
      ${fingerCurled(29, 46)}
      ${fingerCurled(35, 48)}
      ${fingerCurled(41, 50)}
      ${thumbOut()}
      <path d="M22 8 L22 48 L5 55" fill="none" stroke="#667eea" stroke-width="1.5" stroke-dasharray="3 2" opacity="0.5"/>
    </svg>`,

    // M: Three fingers over thumb
    M: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <path d="M16 48 Q16 38 19 40 Q21 42 19 48" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M22 46 Q22 36 25 38 Q27 40 25 46" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M28 46 Q28 36 31 38 Q33 40 31 46" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      ${fingerCurled(36, 48)}
      <path d="M10 56 Q7 48 13 44" fill="none" stroke="#A0785A" stroke-width="2" stroke-linecap="round"/>
      <text x="17" y="36" font-size="7" fill="#667eea" font-weight="bold">3</text>
    </svg>`,

    // N: Two fingers over thumb
    N: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <path d="M18 48 Q18 38 21 40 Q23 42 21 48" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M24 46 Q24 36 27 38 Q29 40 27 46" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      ${fingerCurled(32, 46)}
      ${fingerCurled(38, 48)}
      <path d="M10 56 Q7 48 13 44" fill="none" stroke="#A0785A" stroke-width="2" stroke-linecap="round"/>
      <text x="19" y="36" font-size="7" fill="#667eea" font-weight="bold">2</text>
    </svg>`,

    // O: All fingertips touch thumb forming O
    O: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="30" cy="40" rx="16" ry="20" fill="#FFD5B8" stroke="#A0785A" stroke-width="2.5"/>
      <ellipse cx="30" cy="40" rx="6" ry="9" fill="#f0f2ff" stroke="#A0785A" stroke-width="1.5"/>
    </svg>`,

    // P: Like K but pointing down
    P: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <rect x="14" y="14" width="32" height="28" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="18" y="42" width="7" height="30" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="28" y="42" width="7" height="26" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(15 31 42)"/>
      <path d="M12 24 L6 18" fill="none" stroke="#A0785A" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M10 75 L50 75" fill="none" stroke="#667eea" stroke-width="1" stroke-dasharray="2 2" opacity="0.4"/>
      <text x="42" y="80" font-size="6" fill="#667eea">down</text>
    </svg>`,

    // Q: Like G but pointing down
    Q: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      <rect x="14" y="14" width="32" height="28" rx="6" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="22" y="42" width="7" height="28" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="32" y="42" width="7" height="24" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <path d="M10 75 L50 75" fill="none" stroke="#667eea" stroke-width="1" stroke-dasharray="2 2" opacity="0.4"/>
      <text x="42" y="80" font-size="6" fill="#667eea">down</text>
    </svg>`,

    // R: Index + middle crossed
    R: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <rect x="19" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(5 22 48)"/>
      <rect x="28" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(-5 31 48)"/>
      <path d="M22 20 L34 20" fill="none" stroke="#667eea" stroke-width="1.5" opacity="0.6"/>
      <text x="37" y="18" font-size="6" fill="#667eea">cross</text>
      ${fingerCurled(35, 48)}
      ${fingerCurled(41, 50)}
      ${thumbAcross(68)}
    </svg>`,

    // S: Tight fist, thumb across front
    S: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(16, 48)}
      ${fingerCurled(23, 46)}
      ${fingerCurled(30, 46)}
      ${fingerCurled(37, 48)}
      ${thumbAcross(42)}
    </svg>`,

    // T: Thumb between index and middle
    T: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(16, 48)}
      ${fingerCurled(23, 46)}
      ${fingerCurled(30, 46)}
      ${fingerCurled(37, 48)}
      <path d="M10 54 Q6 44 14 38 Q18 36 22 40" fill="#FFD5B8" stroke="#A0785A" stroke-width="2" stroke-linecap="round"/>
      <circle cx="19" cy="39" r="2" fill="#667eea" opacity="0.6"/>
    </svg>`,

    // U: Index + middle up together
    U: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(21, 4, 46)}
      ${fingerUp(28, 4, 46)}
      ${fingerCurled(35, 48)}
      ${fingerCurled(41, 50)}
      ${thumbAcross(68)}
      <path d="M24 2 L32 2" fill="none" stroke="#667eea" stroke-width="1.5" opacity="0.5"/>
    </svg>`,

    // V: Index + middle spread apart (peace sign)
    V: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <rect x="16" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(-10 19 48)"/>
      <rect x="32" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(10 35 48)"/>
      ${fingerCurled(35, 50)}
      ${fingerCurled(41, 52)}
      ${thumbAcross(68)}
    </svg>`,

    // W: Three fingers up and spread
    W: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <rect x="12" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(-8 15 48)"/>
      <rect x="24" y="4" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      <rect x="36" y="6" width="7" height="42" rx="3.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5" transform="rotate(8 39 48)"/>
      ${fingerCurled(41, 50)}
      ${thumbAcross(68)}
    </svg>`,

    // X: Index finger hooked/bent
    X: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      <path d="M22 48 L22 28 Q22 22 28 26 L28 35" fill="none" stroke="#A0785A" stroke-width="3" stroke-linecap="round"/>
      <circle cx="28" cy="35" r="2.5" fill="#FFD5B8" stroke="#A0785A" stroke-width="1.5"/>
      ${fingerCurled(29, 46)}
      ${fingerCurled(35, 48)}
      ${fingerCurled(41, 50)}
      ${thumbAcross(68)}
    </svg>`,

    // Y: Thumb + pinky out (shaka/hang loose)
    Y: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerCurled(18, 48)}
      ${fingerCurled(25, 46)}
      ${fingerCurled(32, 46)}
      ${fingerUp(39, 10, 48)}
      ${thumbOut()}
    </svg>`,

    // Z: Index pointing with Z motion
    Z: `<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg">
      ${PALM}
      ${fingerUp(22, 10, 46)}
      ${fingerCurled(29, 46)}
      ${fingerCurled(35, 48)}
      ${fingerCurled(41, 50)}
      ${thumbAcross(68)}
      <path d="M16 4 L36 4 L16 20 L36 20" fill="none" stroke="#667eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <polygon points="34,18 38,20 34,22" fill="#667eea"/>
    </svg>`
  };

  function getSVG(letter) {
    return signs[letter.toUpperCase()] || '';
  }

  return { getSVG, signs };
})();
