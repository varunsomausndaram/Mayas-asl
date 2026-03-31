/**
 * ASL Hand Sign Images
 * Uses public domain SVG hand illustrations from Wikimedia Commons.
 * Source: https://commons.wikimedia.org/wiki/Category:ASL_letters
 * License: Public Domain
 *
 * Primary: Wikimedia Commons Special:FilePath (browser-redirect, works in <img> tags)
 * Fallback: inline SVG letter-shaped placeholders if images fail to load
 */

const HandSigns = (() => {

  // Wikimedia Commons public domain ASL alphabet images
  // Special:FilePath provides a stable redirect to the actual upload URL
  function getImageUrl(letter) {
    const L = letter.toUpperCase();
    return `https://commons.wikimedia.org/wiki/Special:FilePath/Sign_language_${L}.svg`;
  }

  // Returns an <img> tag for the letter with a fallback
  function getImgTag(letter, size) {
    const L = letter.toUpperCase();
    const sz = size || 'card'; // 'card' or 'detail'
    const cls = sz === 'detail' ? 'asl-sign-img detail' : 'asl-sign-img';
    return `<img class="${cls}" src="${getImageUrl(L)}" alt="ASL sign for ${L}" loading="lazy" onerror="this.onerror=null;this.parentElement.innerHTML='<div class=\\'asl-fallback\\'>${L}</div>'"/>`;
  }

  // For backwards compat with code that calls getSVG
  function getSVG(letter) {
    return getImgTag(letter, 'card');
  }

  return { getSVG, getImgTag, getImageUrl };
})();
