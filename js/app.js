/**
 * Maya's ASL Adventure — Main App
 * Gamification, navigation, quiz, spelling, progress tracking.
 */

const app = (() => {
  // ===== STATE =====
  let state = {
    xp: 0,
    level: 1,
    streak: 0,
    bestStreak: 0,
    lettersLearned: {},    // { A: true, B: true, ... }
    lettersPracticed: {},   // { A: 3, B: 1, ... } count of correct practices
    dailyCount: 0,
    dailyDate: null,
    badges: {},
    quizHighScore: 0,
    totalQuizzes: 0,
    wordsSpelled: 0
  };

  const XP_PER_LEVEL = 100;

  // ===== WORD LISTS FOR SPELLING =====
  const SPELL_WORDS = {
    animals: ['CAT', 'DOG', 'FISH', 'BIRD', 'FROG', 'BEAR', 'LION', 'DUCK', 'COW', 'PIG'],
    colors: ['RED', 'BLUE', 'PINK', 'GOLD', 'LIME', 'TEAL', 'GRAY'],
    food: ['CAKE', 'PIE', 'RICE', 'CORN', 'MILK', 'SOUP', 'TACO', 'PLUM'],
    family: ['MOM', 'DAD', 'SIS', 'BRO', 'GRAN', 'AUNT', 'BABY'],
    school: ['BOOK', 'PEN', 'MATH', 'READ', 'DESK', 'BELL', 'TEST'],
    names: ['MAYA', 'ALEX', 'LUNA', 'JACK', 'LILY', 'NOAH', 'EMMA']
  };

  // ===== BADGES =====
  const BADGE_DEFS = [
    { id: 'first_sign', name: 'First Sign!', icon: '🌟', desc: 'Practice your first letter', check: s => Object.keys(s.lettersPracticed).length >= 1 },
    { id: 'five_letters', name: 'High Five', icon: '🖐️', desc: 'Learn 5 letters', check: s => Object.keys(s.lettersLearned).length >= 5 },
    { id: 'ten_letters', name: 'Perfect 10', icon: '🔟', desc: 'Learn 10 letters', check: s => Object.keys(s.lettersLearned).length >= 10 },
    { id: 'alphabet_master', name: 'ABC Master', icon: '👑', desc: 'Learn all 26 letters', check: s => Object.keys(s.lettersLearned).length >= 26 },
    { id: 'streak_3', name: 'On Fire!', icon: '🔥', desc: 'Get a 3-letter streak', check: s => s.bestStreak >= 3 },
    { id: 'streak_10', name: 'Unstoppable', icon: '💪', desc: 'Get a 10-letter streak', check: s => s.bestStreak >= 10 },
    { id: 'quiz_star', name: 'Quiz Star', icon: '⭐', desc: 'Complete your first quiz', check: s => s.totalQuizzes >= 1 },
    { id: 'quiz_pro', name: 'Quiz Pro', icon: '🏆', desc: 'Complete 5 quizzes', check: s => s.totalQuizzes >= 5 },
    { id: 'speller', name: 'Spellcaster', icon: '✨', desc: 'Spell your first word', check: s => s.wordsSpelled >= 1 },
    { id: 'word_wizard', name: 'Word Wizard', icon: '🧙', desc: 'Spell 10 words', check: s => s.wordsSpelled >= 10 },
    { id: 'level_5', name: 'Rising Star', icon: '🌠', desc: 'Reach level 5', check: s => s.level >= 5 },
    { id: 'level_10', name: 'ASL Hero', icon: '🦸', desc: 'Reach level 10', check: s => s.level >= 10 },
    { id: 'xp_500', name: 'XP Hunter', icon: '💎', desc: 'Earn 500 XP', check: s => s.xp >= 500 },
    { id: 'daily_done', name: 'Daily Star', icon: '📅', desc: 'Complete a daily challenge', check: s => s.dailyCount >= 5 }
  ];

  // ===== FUN FACTS =====
  const FUN_FACTS = [
    { emoji: '🌍', text: '<strong>ASL is its own language!</strong> It\'s not just English with hand signs — it has its own grammar and sentence structure.' },
    { emoji: '🇫🇷', text: '<strong>ASL came from France!</strong> A French teacher named Laurent Clerc helped create the first American school for the deaf in 1817.' },
    { emoji: '🧠', text: '<strong>Signing uses both sides of your brain!</strong> Learning sign language actually makes your brain stronger.' },
    { emoji: '👶', text: '<strong>Babies can sign before they can talk!</strong> Some babies learn basic signs as young as 6 months old.' },
    { emoji: '🦍', text: '<strong>A gorilla learned sign language!</strong> Koko the gorilla knew over 1,000 signs and could understand 2,000 English words.' },
    { emoji: '🏈', text: '<strong>Football huddles exist because of deaf players!</strong> Gallaudet University\'s deaf football team invented the huddle to keep their signs secret.' },
    { emoji: '🌎', text: '<strong>There are over 300 sign languages worldwide!</strong> British Sign Language is completely different from ASL.' },
    { emoji: '🤟', text: '<strong>The "I Love You" sign</strong> combines the letters I, L, and Y all in one hand shape!' },
    { emoji: '📺', text: '<strong>ASL is the 3rd most used language in the US!</strong> Millions of people communicate using ASL every day.' },
    { emoji: '🎭', text: '<strong>Facial expressions are grammar in ASL!</strong> Raising your eyebrows means you\'re asking a yes/no question.' },
    { emoji: '✊', text: '<strong>Deaf culture has its own art, poetry, and humor!</strong> ASL poetry uses handshapes and movement like rhyming.' },
    { emoji: '🏫', text: '<strong>Gallaudet University</strong> in Washington, D.C. is the only university designed entirely for deaf and hard-of-hearing students.' },
    { emoji: '🎬', text: '<strong>The first deaf actor won an Oscar!</strong> Marlee Matlin won Best Actress in 1987 for the movie "Children of a Lesser God."' },
    { emoji: '📱', text: '<strong>Video calls changed everything!</strong> Deaf people can now sign to each other over phones and computers.' }
  ];

  // ===== LEARNING ORDER =====
  const DIFFICULTY_ORDER = {
    easy: ['A', 'B', 'C', 'L', 'O', 'S', 'V', 'W', 'Y', 'I', 'U'],
    medium: ['D', 'E', 'F', 'R', 'T', 'X', 'K'],
    hard: ['G', 'H', 'J', 'M', 'N', 'P', 'Q', 'Z']
  };

  // ===== PERSISTENCE =====
  function saveState() {
    try { localStorage.setItem('asl_adventure_state', JSON.stringify(state)); } catch (e) {}
  }

  function loadState() {
    try {
      const saved = localStorage.getItem('asl_adventure_state');
      if (saved) state = { ...state, ...JSON.parse(saved) };
    } catch (e) {}
  }

  // ===== XP & LEVELING =====
  function addXP(amount) {
    state.xp += amount;
    const newLevel = Math.floor(state.xp / XP_PER_LEVEL) + 1;
    if (newLevel > state.level) {
      state.level = newLevel;
      showCelebration('🎉', 'Level Up!', `You reached Level ${newLevel}!`);
    }
    checkBadges();
    saveState();
    updateHomeUI();
  }

  // ===== BADGE CHECKING =====
  function checkBadges() {
    for (const badge of BADGE_DEFS) {
      if (!state.badges[badge.id] && badge.check(state)) {
        state.badges[badge.id] = true;
        setTimeout(() => {
          showCelebration(badge.icon, badge.name, badge.desc);
        }, 500);
      }
    }
    saveState();
  }

  // ===== CELEBRATION =====
  function showCelebration(emoji, title, text) {
    const el = document.getElementById('celebration');
    document.getElementById('celebration-emoji').textContent = emoji;
    document.getElementById('celebration-title').textContent = title;
    document.getElementById('celebration-text').textContent = text;
    el.classList.remove('hidden');

    // Confetti
    const container = document.getElementById('confetti');
    container.innerHTML = '';
    const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFEAA7', '#DDA0DD', '#667eea', '#f093fb'];
    for (let i = 0; i < 40; i++) {
      const piece = document.createElement('div');
      piece.className = 'confetti-piece';
      piece.style.left = Math.random() * 100 + '%';
      piece.style.background = colors[Math.floor(Math.random() * colors.length)];
      piece.style.animationDelay = Math.random() * 2 + 's';
      piece.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
      piece.style.width = (Math.random() * 8 + 6) + 'px';
      piece.style.height = (Math.random() * 8 + 6) + 'px';
      container.appendChild(piece);
    }

    setTimeout(() => { el.classList.add('hidden'); }, 3000);
  }

  // ===== DAILY CHALLENGE =====
  function checkDaily() {
    const today = new Date().toDateString();
    if (state.dailyDate !== today) {
      state.dailyDate = today;
      state.dailyCount = 0;
      saveState();
    }
    const el = document.getElementById('daily-progress');
    if (el) el.textContent = `${Math.min(state.dailyCount, 5)}/5`;
  }

  function incrementDaily() {
    state.dailyCount++;
    if (state.dailyCount === 5) {
      addXP(50); // bonus XP for completing daily
    }
    checkDaily();
    saveState();
  }

  // ===== UI UPDATES =====
  function updateHomeUI() {
    const xpInLevel = state.xp % XP_PER_LEVEL;
    const pct = (xpInLevel / XP_PER_LEVEL) * 100;

    const fill = document.getElementById('home-xp-fill');
    const text = document.getElementById('home-xp-text');
    if (fill) fill.style.width = pct + '%';
    if (text) text.textContent = `Level ${state.level} — ${xpInLevel}/${XP_PER_LEVEL} XP`;

    const streakEl = document.getElementById('streak-count');
    if (streakEl) streakEl.textContent = state.bestStreak;

    checkDaily();

    // Alphabet progress dots
    const container = document.getElementById('alphabet-progress');
    if (container) {
      container.innerHTML = '';
      for (let i = 0; i < 26; i++) {
        const letter = String.fromCharCode(65 + i);
        const dot = document.createElement('div');
        dot.className = 'alpha-dot';
        if (state.lettersLearned[letter]) dot.classList.add('learned');
        else if (state.lettersPracticed[letter]) dot.classList.add('in-progress');
        dot.textContent = letter;
        container.appendChild(dot);
      }
    }
  }

  // ===== NAVIGATION =====
  function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const screen = document.getElementById(screenId);
    if (screen) screen.classList.add('active');

    if (screenId === 'home-screen') updateHomeUI();
    if (screenId === 'learn-screen') renderLearnGrid('all');
    if (screenId === 'achievements-screen') renderAchievements();
    if (screenId === 'funfacts-screen') renderFunFacts();
    if (screenId === 'quiz-screen') {
      document.getElementById('quiz-setup').classList.remove('hidden');
      document.getElementById('quiz-game').classList.add('hidden');
      document.getElementById('quiz-results').classList.add('hidden');
    }
    if (screenId === 'spell-screen') {
      document.getElementById('spell-setup').classList.remove('hidden');
      document.getElementById('spell-game').classList.add('hidden');
    }
  }

  // ===== LEARN SCREEN =====
  function setLearnTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    renderLearnGrid(tab);
  }

  function renderLearnGrid(filter) {
    const grid = document.getElementById('letter-grid');
    grid.innerHTML = '';

    let letters;
    if (filter === 'all') letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    else if (filter === 'easy') letters = DIFFICULTY_ORDER.easy;
    else if (filter === 'medium') letters = DIFFICULTY_ORDER.medium;
    else letters = DIFFICULTY_ORDER.hard;

    for (const letter of letters) {
      const data = ASLClassifier.getLetterData(letter);
      if (!data) continue;

      const card = document.createElement('button');
      card.className = 'letter-card';
      card.onclick = () => showLetterDetail(letter);

      const diffClass = 'diff-' + data.difficulty;
      const learned = state.lettersLearned[letter];

      card.innerHTML = `
        ${learned ? '<span class="learned-check">✅</span>' : ''}
        <div class="letter-big">${letter}</div>
        <div class="letter-svg">${HandSigns.getSVG(letter)}</div>
        <span class="letter-difficulty ${diffClass}">${data.difficulty}</span>
      `;
      grid.appendChild(card);
    }
  }

  // ===== LETTER DETAIL =====
  function showLetterDetail(letter) {
    const data = ASLClassifier.getLetterData(letter);
    if (!data) return;

    document.getElementById('letter-detail-title').textContent = `Letter ${letter}`;
    document.getElementById('detail-big-letter').textContent = letter;
    document.getElementById('letter-instructions').innerHTML = `
      <h3>How to Sign "${letter}"</h3>
      <p>${data.description}</p>
    `;
    document.getElementById('hand-diagram').innerHTML = HandSigns.getSVG(letter);
    document.getElementById('finger-checklist').innerHTML = `
      <h4>Hand Position:</h4>
      ${data.fingers.split('. ').map(f => f.trim()).filter(Boolean).map(f =>
        `<div class="checklist-item"><span class="check">✓</span> ${f}</div>`
      ).join('')}
    `;
    document.getElementById('letter-tip').innerHTML = `💡 <strong>Tip:</strong> ${data.tip}`;

    currentPracticeLetter = letter;
    showScreen('letter-detail-screen');

    // Mark as viewed
    if (!state.lettersLearned[letter]) {
      state.lettersLearned[letter] = true;
      addXP(5);
    }
  }

  // ===== PRACTICE MODE =====
  let currentPracticeLetter = 'A';
  let practiceActive = false;

  function practiceThisLetter() {
    showScreen('practice-screen');
    document.getElementById('practice-target').textContent = currentPracticeLetter;
    startPracticeCamera();
  }

  async function startPracticeCamera() {
    practiceActive = true;
    const video = document.getElementById('camera-feed');
    const canvas = document.getElementById('hand-overlay');
    const statusDot = document.querySelector('#detection-status .status-dot');
    const statusText = document.querySelector('#detection-status .status-text');

    const ok = await HandDetector.startCamera(video);
    if (!ok) {
      document.getElementById('feedback-text').textContent = 'Could not access camera. Please allow camera permission and try again.';
      return;
    }

    ASLClassifier.resetStability();

    HandDetector.startDetection(video, canvas, (landmarks, handDetected) => {
      if (!practiceActive) return;

      if (handDetected) {
        statusDot.classList.add('active');
        statusText.textContent = 'Hand detected!';

        const result = ASLClassifier.classifyStable(landmarks);
        const display = document.getElementById('detected-letter-display');
        const feedbackIcon = document.getElementById('feedback-icon');
        const feedbackText = document.getElementById('feedback-text');

        if (result) {
          display.textContent = result.letter;

          if (result.letter === currentPracticeLetter) {
            feedbackIcon.textContent = '🎉';
            feedbackText.textContent = `Perfect! That's ${currentPracticeLetter}! Great job!`;
            display.style.background = 'rgba(46, 204, 113, 0.8)';

            // Record success
            state.lettersPracticed[currentPracticeLetter] = (state.lettersPracticed[currentPracticeLetter] || 0) + 1;
            state.streak++;
            if (state.streak > state.bestStreak) state.bestStreak = state.streak;
            addXP(10);
            incrementDaily();

            // Auto-advance after a moment
            setTimeout(() => {
              if (practiceActive) nextPracticeLetter();
            }, 1500);
          } else {
            feedbackIcon.textContent = '🤔';
            feedbackText.textContent = `That looks like "${result.letter}". Try adjusting for "${currentPracticeLetter}"!`;
            display.style.background = 'rgba(243, 156, 18, 0.8)';
          }
        } else {
          display.textContent = '?';
          display.style.background = 'rgba(102, 126, 234, 0.7)';
          feedbackIcon.textContent = '👋';
          feedbackText.textContent = 'Hold your hand steady...';
        }
      } else {
        statusDot.classList.remove('active');
        statusText.textContent = 'Waiting for hand...';
        document.getElementById('detected-letter-display').textContent = '';
        document.getElementById('feedback-icon').textContent = '📷';
        document.getElementById('feedback-text').textContent = 'Show your hand to the camera!';
      }
    });
  }

  function nextPracticeLetter() {
    ASLClassifier.resetStability();
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const idx = letters.indexOf(currentPracticeLetter);
    currentPracticeLetter = letters[(idx + 1) % 26];
    document.getElementById('practice-target').textContent = currentPracticeLetter;
    document.getElementById('detected-letter-display').textContent = '';
    document.getElementById('detected-letter-display').style.background = 'rgba(102, 126, 234, 0.7)';
    document.getElementById('feedback-text').textContent = `Now try "${currentPracticeLetter}"!`;
    document.getElementById('feedback-icon').textContent = '👉';

    // Hide hint
    const hintContent = document.getElementById('hint-content');
    if (hintContent) hintContent.classList.remove('visible');
  }

  function showPracticeHint() {
    const data = ASLClassifier.getLetterData(currentPracticeLetter);
    const hintContent = document.getElementById('hint-content');
    if (data && hintContent) {
      hintContent.innerHTML = `<strong>${currentPracticeLetter}:</strong> ${data.description}<br><em>${data.tip}</em>`;
      hintContent.classList.toggle('visible');
    }
  }

  function stopPractice() {
    practiceActive = false;
    HandDetector.stopDetection();
    HandDetector.stopCamera(document.getElementById('camera-feed'));
    showScreen('home-screen');
  }

  // ===== QUIZ MODE =====
  let quizState = null;
  let quizTimerInterval = null;

  function startQuiz(difficulty) {
    const configs = {
      easy: { count: 5, time: 15 },
      medium: { count: 10, time: 10 },
      hard: { count: 15, time: 7 },
      speed: { count: 26, time: 5 }
    };
    const config = configs[difficulty];

    // Pick random letters
    let pool = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    if (difficulty === 'easy') pool = DIFFICULTY_ORDER.easy.slice();
    pool.sort(() => Math.random() - 0.5);
    const letters = pool.slice(0, config.count);

    quizState = {
      letters,
      timePerLetter: config.time,
      currentIndex: 0,
      score: 0,
      correct: 0,
      streak: 0,
      bestStreak: 0,
      missed: [],
      answered: false
    };

    document.getElementById('quiz-setup').classList.add('hidden');
    document.getElementById('quiz-results').classList.add('hidden');
    document.getElementById('quiz-game').classList.remove('hidden');
    document.getElementById('quiz-total').textContent = letters.length;

    startQuizRound();
  }

  async function startQuizRound() {
    if (!quizState || quizState.currentIndex >= quizState.letters.length) {
      endQuiz();
      return;
    }

    quizState.answered = false;
    const letter = quizState.letters[quizState.currentIndex];

    document.getElementById('quiz-letter').textContent = letter;
    document.getElementById('quiz-current').textContent = quizState.currentIndex + 1;
    document.getElementById('quiz-score').textContent = quizState.score;
    document.getElementById('quiz-streak').textContent = quizState.streak;
    document.getElementById('quiz-result-overlay').classList.add('hidden');

    // Start camera if not running
    const video = document.getElementById('quiz-camera-feed');
    const canvas = document.getElementById('quiz-hand-overlay');

    if (!video.srcObject) {
      await HandDetector.startCamera(video);
    }

    ASLClassifier.resetStability();

    HandDetector.startDetection(video, canvas, (landmarks, detected) => {
      if (!quizState || quizState.answered) return;

      if (detected) {
        const result = ASLClassifier.classifyStable(landmarks);
        if (result && result.letter === letter) {
          quizState.answered = true;
          quizCorrect();
        }
      }
    });

    // Timer
    let timeLeft = quizState.timePerLetter;
    document.getElementById('timer-text').textContent = timeLeft;
    updateTimerRing(timeLeft, quizState.timePerLetter);

    clearInterval(quizTimerInterval);
    quizTimerInterval = setInterval(() => {
      timeLeft--;
      document.getElementById('timer-text').textContent = timeLeft;
      updateTimerRing(timeLeft, quizState.timePerLetter);

      const fill = document.getElementById('timer-fill');
      if (timeLeft <= 3) fill.classList.add('danger');
      else fill.classList.remove('danger');

      if (timeLeft <= 0) {
        clearInterval(quizTimerInterval);
        if (!quizState.answered) {
          quizState.answered = true;
          quizWrong();
        }
      }
    }, 1000);
  }

  function updateTimerRing(timeLeft, total) {
    const pct = (timeLeft / total) * 100;
    const offset = 100 - pct;
    document.getElementById('timer-fill').style.strokeDashoffset = offset;
  }

  function quizCorrect() {
    clearInterval(quizTimerInterval);
    HandDetector.stopDetection();

    quizState.correct++;
    quizState.streak++;
    if (quizState.streak > quizState.bestStreak) quizState.bestStreak = quizState.streak;

    // Score: base + time bonus + streak bonus
    const points = 10 + quizState.streak * 2;
    quizState.score += points;

    const overlay = document.getElementById('quiz-result-overlay');
    document.getElementById('quiz-result-emoji').textContent = quizState.streak >= 3 ? '🔥' : '✅';
    overlay.classList.remove('hidden');

    document.getElementById('quiz-score').textContent = quizState.score;
    document.getElementById('quiz-streak').textContent = quizState.streak;

    setTimeout(() => {
      quizState.currentIndex++;
      startQuizRound();
    }, 1000);
  }

  function quizWrong() {
    clearInterval(quizTimerInterval);
    HandDetector.stopDetection();

    quizState.missed.push(quizState.letters[quizState.currentIndex]);
    quizState.streak = 0;

    const overlay = document.getElementById('quiz-result-overlay');
    document.getElementById('quiz-result-emoji').textContent = '⏰';
    overlay.classList.remove('hidden');

    document.getElementById('quiz-streak').textContent = 0;

    setTimeout(() => {
      quizState.currentIndex++;
      startQuizRound();
    }, 1200);
  }

  function endQuiz() {
    HandDetector.stopDetection();
    HandDetector.stopCamera(document.getElementById('quiz-camera-feed'));
    clearInterval(quizTimerInterval);

    const q = quizState;
    state.totalQuizzes++;
    if (q.score > state.quizHighScore) state.quizHighScore = q.score;
    if (q.bestStreak > state.bestStreak) state.bestStreak = q.bestStreak;

    const xpEarned = q.score + (q.correct === q.letters.length ? 25 : 0);
    addXP(xpEarned);

    // Show results
    document.getElementById('quiz-game').classList.add('hidden');
    document.getElementById('quiz-results').classList.remove('hidden');

    const pct = q.correct / q.letters.length;
    let emoji, title;
    if (pct === 1) { emoji = '🏆'; title = 'PERFECT!'; }
    else if (pct >= 0.8) { emoji = '🎉'; title = 'Amazing!'; }
    else if (pct >= 0.5) { emoji = '👍'; title = 'Good Job!'; }
    else { emoji = '💪'; title = 'Keep Practicing!'; }

    document.getElementById('results-emoji').textContent = emoji;
    document.getElementById('results-title').textContent = title;
    document.getElementById('result-score').textContent = q.score;
    document.getElementById('result-correct').textContent = `${q.correct}/${q.letters.length}`;
    document.getElementById('result-streak').textContent = q.bestStreak;
    document.getElementById('result-xp').textContent = `+${xpEarned} XP`;

    if (q.missed.length > 0) {
      document.getElementById('results-missed').innerHTML =
        `<p>Practice these: <strong>${q.missed.join(', ')}</strong></p>`;
    } else {
      document.getElementById('results-missed').innerHTML = '';
    }

    quizState = null;
  }

  function stopQuiz() {
    if (quizTimerInterval) clearInterval(quizTimerInterval);
    HandDetector.stopDetection();
    HandDetector.stopCamera(document.getElementById('quiz-camera-feed'));
    quizState = null;
    showScreen('home-screen');
  }

  // ===== SPELL MODE =====
  let spellState = null;

  function startSpell(category) {
    const words = SPELL_WORDS[category] || SPELL_WORDS.animals;
    const word = words[Math.floor(Math.random() * words.length)];

    spellState = {
      word,
      currentIndex: 0,
      category
    };

    document.getElementById('spell-setup').classList.add('hidden');
    document.getElementById('spell-game').classList.remove('hidden');

    document.getElementById('spell-word').textContent = `Spell: ${word}`;
    renderSpellLetters();
    startSpellCamera();
  }

  function renderSpellLetters() {
    const container = document.getElementById('spell-letters');
    container.innerHTML = '';
    for (let i = 0; i < spellState.word.length; i++) {
      const el = document.createElement('div');
      el.className = 'spell-char';
      if (i < spellState.currentIndex) el.classList.add('done');
      else if (i === spellState.currentIndex) el.classList.add('current');
      el.textContent = spellState.word[i];
      container.appendChild(el);
    }
    const pct = (spellState.currentIndex / spellState.word.length) * 100;
    document.getElementById('spell-progress-fill').style.width = pct + '%';
  }

  async function startSpellCamera() {
    const video = document.getElementById('spell-camera-feed');
    const canvas = document.getElementById('spell-hand-overlay');

    await HandDetector.startCamera(video);
    ASLClassifier.resetStability();

    HandDetector.startDetection(video, canvas, (landmarks, detected) => {
      if (!spellState) return;

      if (detected) {
        const result = ASLClassifier.classifyStable(landmarks);
        const targetLetter = spellState.word[spellState.currentIndex];

        if (result && result.letter === targetLetter) {
          spellState.currentIndex++;
          ASLClassifier.resetStability();
          renderSpellLetters();

          if (spellState.currentIndex >= spellState.word.length) {
            // Word complete!
            document.getElementById('spell-feedback').textContent = `🎉 You spelled "${spellState.word}"! Amazing!`;
            state.wordsSpelled++;
            addXP(20);
            checkBadges();

            HandDetector.stopDetection();

            setTimeout(() => {
              // Start a new word from same category
              startSpell(spellState.category);
            }, 2500);
          } else {
            const next = spellState.word[spellState.currentIndex];
            document.getElementById('spell-feedback').textContent = `Great! Now sign "${next}"`;
          }
        } else if (result) {
          document.getElementById('spell-feedback').textContent =
            `That's "${result.letter}" — looking for "${targetLetter}"`;
        } else {
          document.getElementById('spell-feedback').textContent = `Sign the letter "${targetLetter}"`;
        }
      } else {
        const targetLetter = spellState.word[spellState.currentIndex];
        document.getElementById('spell-feedback').textContent = `Show me "${targetLetter}"!`;
      }
    });
  }

  function stopSpell() {
    HandDetector.stopDetection();
    HandDetector.stopCamera(document.getElementById('spell-camera-feed'));
    spellState = null;
    showScreen('home-screen');
  }

  // ===== ACHIEVEMENTS =====
  function renderAchievements() {
    document.getElementById('total-xp').textContent = state.xp;
    document.getElementById('letters-learned').textContent = Object.keys(state.lettersLearned).length;
    document.getElementById('best-streak-stat').textContent = state.bestStreak;

    const grid = document.getElementById('badges-grid');
    grid.innerHTML = '';

    for (const badge of BADGE_DEFS) {
      const unlocked = state.badges[badge.id];
      const card = document.createElement('div');
      card.className = 'badge-card' + (unlocked ? '' : ' locked');
      card.innerHTML = `
        <div class="badge-icon">${unlocked ? badge.icon : '🔒'}</div>
        <div class="badge-name">${badge.name}</div>
        <div class="badge-desc">${badge.desc}</div>
      `;
      grid.appendChild(card);
    }
  }

  // ===== FUN FACTS =====
  function renderFunFacts() {
    const container = document.getElementById('funfacts-container');
    container.innerHTML = '';
    for (const fact of FUN_FACTS) {
      const card = document.createElement('div');
      card.className = 'fact-card';
      card.innerHTML = `
        <div class="fact-emoji">${fact.emoji}</div>
        <div class="fact-text">${fact.text}</div>
      `;
      container.appendChild(card);
    }
  }

  // ===== GREETING =====
  function getGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return ['Good Morning! ☀️', 'Rise and sign!'];
    if (hour < 17) return ['Good Afternoon! 🌤️', 'Let\'s practice some ASL!'];
    return ['Good Evening! 🌙', 'Time for some signing fun!'];
  }

  // ===== INIT =====
  async function init() {
    loadState();

    const [title, sub] = getGreeting();
    document.getElementById('greeting-text').textContent = title;
    document.getElementById('greeting-sub').textContent = sub;

    // Init hand detector with progress
    const fill = document.getElementById('loading-fill');
    const text = document.getElementById('loading-text');

    const ok = await HandDetector.init((pct, msg) => {
      if (pct >= 0) fill.style.width = pct + '%';
      text.textContent = msg;
    });

    if (ok) {
      fill.style.width = '100%';
      text.textContent = 'Ready! Let\'s go!';
    } else {
      text.textContent = 'Hand detection unavailable — you can still learn!';
    }

    // Show home after brief delay
    setTimeout(() => {
      showScreen('home-screen');
    }, ok ? 800 : 2000);

    // Register service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
  }

  // Start the app
  init();

  // Public API
  return {
    showScreen,
    setLearnTab,
    showLetterDetail,
    practiceThisLetter,
    nextPracticeLetter,
    showPracticeHint,
    stopPractice,
    startQuiz,
    stopQuiz,
    startSpell,
    stopSpell,
    state
  };
})();
