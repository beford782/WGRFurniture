// Central DreamFinder lead backup inbox. Every retailer deployment BCCs this
// address by default so leads roll up centrally. During Apps Script setup,
// review this value:
//   - keep the default to participate in the central backup
//   - replace with a retailer-specific backup inbox if appropriate
//   - set to '' to disable BCC for this deployment
var RESULT_EMAIL_BCC = 'dreamfinderleads@gmail.com';
// Defensive payload ceiling, not a merchandising limit. The kiosk currently
// selects at most one product per Sleep System step, but future stores may add
// more categories and should not silently lose items after the third.
var MAX_EMAIL_ACCESSORIES = 20;

// \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
// CAN-SPAM / privacy footer values \u2014 \u26a0\ufe0f DRAFT PLACEHOLDERS, NOT YET APPROVED.
// WG&R MUST REVIEW & APPROVE every value below BEFORE live lead capture.
// CAN-SPAM requires (a) a working unsubscribe mechanism, honored within 10
// business days and kept live >=30 days, and (b) a valid physical postal
// address in every commercial email. The values here are review drafts only.
// These are WG&R-STYLE GUESSES, NOT confirmed \u2014 the inbox/domain may not exist
// or route, and the postal address is incomplete. Do NOT enable gasUrl until
// WG&R confirms all three AND the unsubscribe inbox is actively monitored.
// Replace all three before going live.
// \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
var UNSUBSCRIBE_URL = 'mailto:unsubscribe@wgrfurniture.com?subject=Unsubscribe%20DreamFinder'; // \u26a0\ufe0f WG&R TO APPROVE (unverified placeholder)
var POSTAL_ADDRESS  = 'WG&R Furniture (TEST DEPLOYMENT), PO Box 0000, Green Bay, WI 54301'; // \u26a0\ufe0f TEST PLACEHOLDER \u2014 WG&R TO APPROVE real address before live
var PRIVACY_CONTACT = 'privacy@wgrfurniture.com'; // \u26a0\ufe0f WG&R TO APPROVE (unverified placeholder)

// Helper: escape five HTML metacharacters; safe for attribute values and text content.
function _escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });
}

// Helper: permissive email shape check; not full RFC 5322. Catches empty / missing-@ / obvious typos.
function _isValidEmail(s) {
  if (typeof s !== 'string') return false;
  var t = s.trim();
  if (t.length < 3 || t.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
}

// Helper: restrict to supported languages; default to 'en'.
function _normalizeLang(s) {
  return s === 'es' ? 'es' : 'en';
}

// Helper: coerce + bound length only. Does NOT strip characters (accents, apostrophes, hyphens, Spanish chars).
function _safeText(s, max) {
  if (s == null) return '';
  var str = String(s);
  if (max && str.length > max) str = str.slice(0, max);
  return str;
}

// Helper: allow https:// URLs and repo-relative images/ paths only. Empty otherwise (existing fallback block renders).
// URL-encodes the result (encodeURI) so filenames with spaces \u2014 e.g.
// "pro breeze 2.0 medium hybrid.jpg" \u2014 become %20 and load in strict clients
// like desktop Gmail's image proxy. encodeURI is idempotent for already-valid
// URLs (leaves :/?#& and existing %XX intact); falls back to the raw value if
// the string can't be encoded.
function _safeImageUrl(url) {
  if (typeof url !== 'string') return '';
  var t = url.trim();
  if (!t) return '';
  var ok = /^https:\/\//i.test(t) || /^images\//.test(t);
  if (!ok) return '';
  try { return encodeURI(t); } catch (e) { return t; }
}

// Helper: coerce to array; returns [] for non-array inputs.
function _safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // Shape-only summary; full PII (email/name/phone) shouldn't persist in GAS logs.
    Logger.log('doPost received: name_len=' + (data.name ? String(data.name).length : 0)
      + ', email=' + (data.email ? 'set' : 'unset')
      + ', phone=' + (data.phone ? 'set' : 'unset')
      + ', matches=' + ((data.allMatches || []).length)
      + ', accessories=' + ((data.accessories || []).length)
      + ', lang=' + (data.lang || ''));

    var lang = _normalizeLang(data.lang);
    var isEs = lang === 'es';

    var email = (data.email || '').toString().trim();
    if (!_isValidEmail(email)) {
      Logger.log('doPost rejected: invalid_email');
      return ContentService
        .createTextOutput(JSON.stringify({ success: false, error: 'invalid_email' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // Bound client-controlled scalars defensively.
    var name = _safeText(data.name, 200);
    var phone = _safeText(data.phone, 40);
    var dreamCode = _safeText(data.dreamCode, 40);
    var sleepProfile = _safeText(data.sleepProfile, 500);
    var topMatch = _safeText(data.topMatch, 200);
    var matchPct = _safeText(data.matchPct, 10);
    var meetsMatchThreshold = data.meetsMatchThreshold === true;
    var rsa = _safeText(data.rsa, 100);
    var discount = _safeText(data.discount || 5, 10);
    var passExpiration = _safeText(data.passExpiration, 80) || '30 days from issue';
    var passScope = _safeText(data.passScope, 300) || 'a qualifying DreamFinder mattress selection';
    var passTerms = _safeText(data.passTerms, 1000)
      || 'Valid on qualifying mattress selections. Cannot be combined with other offers. Final eligibility confirmed by your sleep specialist.';

    // White-label store identity, supplied by the client from STORE_CONFIG.storeName.
    // Falls back to a generic phrase so a missing/blank field never leaks another
    // retailer's name. Used below in plain-text contexts (subject / sender / plain
    // fallback body) with NO HTML escaping; buildSimpleHtml re-escapes for HTML.
    var storeName = _safeText(data.storeName, 100).trim() || (isEs ? 'nuestra tienda' : 'our store');

    // --- Log to Google Sheet ---
    // rsa appended at the end (right-of-last column) per the
    // append-don't-insert strategy documented in docs/gas-rsa-field-addition.md.
    // Inserting mid-row would force every other column to re-index. Sheet
    // operator must add a corresponding "rsa" column header to match.
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.appendRow([
      new Date(),
      name,
      email,
      phone,
      dreamCode,
      lang,
      _safeArray(data.allMatches).slice(0, 6).map(function(m) {
        return _safeText(m && m.name, 200) + (m && m.meetsMatchThreshold === true
          ? ' (' + _safeText(m.matchPct, 10) + '%)'
          : ' (additional comparison option)');
      }).join(', '),
      _safeArray(data.accessories).slice(0, MAX_EMAIL_ACCESSORIES).map(function(a) { return _safeText(a && a.name, 200); }).join(', '),
      rsa
    ]);

    // --- Send email with fallback ---
    // Subject leads with the Sleep Brief (the consultation takeaway) and keeps
    // the Savings Pass as a secondary draw, matching the in-app "Save your Sleep
    // Brief" narrative. (Email-body section ORDER still shows the Savings Pass
    // band before the Sleep Brief section; reordering is deferred to the Phase C
    // test deploy where the rendered email can actually be verified.)
    var subject = isEs
      ? 'Tu Resumen de Sue\u00f1o y Pase de Ahorro de ' + storeName
      : 'Your Sleep Brief & Savings Pass from ' + storeName;
    var senderName = isEs
      ? 'Equipo de Descanso de ' + storeName
      : storeName + ' Sleep Team';
    var firstName = (name || (isEs ? 'amigo' : 'there')).split(' ')[0];

    // Pre-bound payload for buildSimpleHtml; image URLs filtered to https:// or images/ only.
    var safeData = {
      dreamCode: dreamCode,
      sleepProfile: sleepProfile,
      topMatch: topMatch,
      matchPct: matchPct,
      meetsMatchThreshold: meetsMatchThreshold,
      discount: discount,
      passExpiration: passExpiration,
      passScope: passScope,
      passTerms: passTerms,
      rsa: rsa,
      allMatches: _safeArray(data.allMatches).slice(0, 6).map(function(m) {
        return {
          name: _safeText(m && m.name, 200),
          brand: _safeText(m && m.brand, 100),
          matchPct: _safeText(m && m.matchPct, 10),
          meetsMatchThreshold: m && m.meetsMatchThreshold === true,
          imageUrl: _safeImageUrl(m && m.imageUrl)
        };
      }),
      accessories: _safeArray(data.accessories).slice(0, MAX_EMAIL_ACCESSORIES).map(function(a) {
        return {
          name: _safeText(a && a.name, 200),
          category: _safeText(a && a.category, 100),
          imageUrl: _safeImageUrl(a && a.imageUrl)
        };
      }),
      // Website-derived WG&R promotions, pre-localized by the client to data.lang.
      promotions: _safeArray(data.emailPromotions).slice(0, 12).map(function(p) {
        return {
          badge: _safeText(p && p.badge, 80),
          headline: _safeText(p && p.headline, 200),
          detail: _safeText(p && p.detail, 400),
          disclosure: _safeText(p && p.disclosure, 400),
          // Optional per-promotion evidence/provenance line (e.g. reconstructed-
          // historical scenarios). Absent in current/website-verified payloads, so
          // it renders only when the client supplies it \u2014 existing behavior intact.
          provenance: _safeText(p && p.provenance, 400),
          expiration: _safeText(p && p.expiration, 80),
          sourceUrl: _safeImageUrl(p && p.sourceUrl)
        };
      }),
      promoSpanishDraft: _safeText(data.promoSpanishDraft, 200),
      // Scenario-level fields (pre-localized by the client). A non-empty
      // promoDisclosure marks a disclosed scenario (e.g. the historical demo):
      // the promo header drops any "current offer" claim and the disclosure is
      // surfaced. Both empty for genuine current scenarios -> behavior unchanged.
      promoScenario: _safeText(data.promoScenario, 80),
      promoDisclosure: _safeText(data.promoDisclosure, 400)
    };

    try {
      // Always build HTML server-side. Client previously sent data.htmlBody but
      // that path was deprecated in 5e \u2014 kiosk no longer ships pre-built HTML.
      var htmlBody = buildSimpleHtml(safeData, firstName, isEs, storeName);
      var plainFallback = isEs
        ? 'Por favor visualiza este correo en un cliente de correo HTML.'
        : 'Please view in an HTML email client.';

      var mailOptions = {
        htmlBody: htmlBody,
        name: senderName
      };
      if (RESULT_EMAIL_BCC) mailOptions.bcc = RESULT_EMAIL_BCC;
      GmailApp.sendEmail(email, subject, plainFallback, mailOptions);

    } catch (emailErr) {
      Logger.log('HTML email failed, trying plain text: ' + emailErr.toString());
      var accessoryLines = safeData.accessories.map(function(a, i) {
        return (i + 1) + '. ' + a.name + (a.category ? ' - ' + a.category : '');
      }).join('\n');
      var promoLines = (safeData.promotions || []).map(function(p) {
        return '- ' + p.badge + ': ' + p.headline
          + (p.detail ? '\n  ' + p.detail : '')
          + (p.disclosure ? '\n  ' + p.disclosure : '')
          + (p.provenance ? '\n  ' + p.provenance : '')
          + (p.expiration ? '\n  ' + p.expiration : '')
          + (p.sourceUrl ? '\n  ' + p.sourceUrl : '');
      }).join('\n');
      // Scenario-aware plain-text promo header: a disclosed scenario (e.g. the
      // historical demo) drops the "current offer" claim and prepends the
      // disclosure line. Empty disclosure -> existing "Current WG&R Offers" header.
      var plainPromoDisclosure = (safeData.promoDisclosure || '').toString();
      var plainPromoHeader = plainPromoDisclosure
        ? (isEs ? 'Ofertas de WG&R' : 'WG&R Offers')
        : (isEs ? 'Ofertas Actuales de WG&R' : 'Current WG&R Offers');
      var promoBlock = promoLines
        ? ('\n\n' + plainPromoHeader + ':\n'
            + (plainPromoDisclosure ? plainPromoDisclosure + '\n' : '')
            + (safeData.promoSpanishDraft && isEs ? safeData.promoSpanishDraft + '\n' : '')
            + promoLines)
        : '';
      var comparisonLabel = isEs ? 'Opci\u00f3n adicional para comparar' : 'Additional comparison option';
      var topMatchDetail = meetsMatchThreshold
        ? matchPct + (isEs ? '% compatibilidad' : '% match')
        : comparisonLabel;
      var plainBody = isEs
        ? ('Tu match de sue\u00f1o WG&R est\u00e1 listo.\n\n'
          + (meetsMatchThreshold ? 'Tu mejor opci\u00f3n: ' : 'Opci\u00f3n para comparar: ') + topMatch + ' (' + topMatchDetail + ')\n'
          + 'El mejor punto de partida en la tienda.\n'
          + 'Resumen de sue\u00f1o: ' + sleepProfile + '\n'
          + 'Tu pase de ahorro de 30 d\u00edas: ' + discount + '% DE DESCUENTO\n'
          + 'C\u00f3digo del pase: ' + dreamCode + '\n\n'
          + 'V\u00e1lido en: ' + passScope + '\n'
          + 'V\u00e1lido hasta: ' + passExpiration + '\n'
          + passTerms + '\n\n'
          + 'Muestra este correo a tu especialista de sue\u00f1o de ' + storeName + '.\n\n'
          + safeData.allMatches.map(function(m, i) {
              return (i+1) + '. ' + m.name + ' - ' + (m.meetsMatchThreshold
                ? m.matchPct + '% compatibilidad'
                : comparisonLabel);
            }).join('\n')
          + (accessoryLines ? '\n\nTu Sistema de Sue\u00f1o guardado:\n' + accessoryLines : '')
          + promoBlock
          + '\n\n----------\n'
          + 'Recibiste este correo porque guardaste tu Resumen de Sue\u00f1o en ' + storeName + '.\n'
          + POSTAL_ADDRESS + '\n'
          + 'Cancelar suscripci\u00f3n: ' + UNSUBSCRIBE_URL + '\n'
          + 'Privacidad y solicitudes de datos: ' + PRIVACY_CONTACT)
        : ('Your WG&R sleep match is ready.\n\n'
          + (meetsMatchThreshold ? 'Your best match: ' : 'Option to compare: ') + topMatch + ' (' + topMatchDetail + ')\n'
          + 'Best place to start in-store.\n'
          + 'Sleep Brief: ' + sleepProfile + '\n'
          + 'Your 30-day Savings Pass: ' + discount + '% OFF\n'
          + 'Savings pass code: ' + dreamCode + '\n\n'
          + 'Valid on: ' + passScope + '\n'
          + 'Good through: ' + passExpiration + '\n'
          + passTerms + '\n\n'
          + 'Show this email to your ' + storeName + ' sleep specialist.\n\n'
          + safeData.allMatches.map(function(m, i) {
              return (i+1) + '. ' + m.name + ' - ' + (m.meetsMatchThreshold
                ? m.matchPct + '% match'
                : comparisonLabel);
            }).join('\n')
          + (accessoryLines ? '\n\nYour saved Sleep System:\n' + accessoryLines : '')
          + promoBlock
          + '\n\n----------\n'
          + 'You received this email because you saved your Sleep Brief at ' + storeName + '.\n'
          + POSTAL_ADDRESS + '\n'
          + 'Unsubscribe: ' + UNSUBSCRIBE_URL + '\n'
          + 'Privacy & data requests: ' + PRIVACY_CONTACT);

      var fallbackOptions = {
        name: senderName
      };
      if (RESULT_EMAIL_BCC) fallbackOptions.bcc = RESULT_EMAIL_BCC;
      GmailApp.sendEmail(email, subject, plainBody, fallbackOptions);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ success: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    // Generic error to browser; full detail stays in GAS logs.
    Logger.log('doPost error: ' + err.toString());
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: 'send_failed' }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function buildSimpleHtml(data, firstName, isEs, storeName) {
  // All user/client-controlled fields below are HTML-escaped at every
  // interpolation site (caller has already _safeText-bounded scalars and
  // _safeImageUrl-filtered image URLs).
  firstName = _escapeHtml(firstName);
  storeName = _escapeHtml(storeName || (isEs ? 'nuestra tienda' : 'our store'));
  var dreamCode = _escapeHtml(data.dreamCode || '');
  // Server-side safety ceilings protect the email renderer from oversized
  // client payloads without imposing the former three-accessory product limit.
  var matches = _safeArray(data.allMatches).slice(0, 6);
  var accs = _safeArray(data.accessories).slice(0, MAX_EMAIL_ACCESSORIES);
  var discount = _escapeHtml(data.discount || 5);
  var passExpiration = _escapeHtml(data.passExpiration || '30 days from issue');
  var passScope = _escapeHtml(data.passScope || 'a qualifying DreamFinder mattress selection');
  var passTerms = _escapeHtml(data.passTerms
    || 'Valid on qualifying mattress selections. Cannot be combined with other offers. Final eligibility confirmed by your sleep specialist.');
  var sleepProfile = _escapeHtml(data.sleepProfile || '');

  var rsa = _escapeHtml((data.rsa || '').toString().trim());

  // WG&R warm-paper palette \u2014 ported from index.html showroom theme
  // (#F3EEE5 / #FFFDF8 / #2F271E ink + brass #9A7445) plus WG&R red from
  // store-config.colors. Light surfaces, dark ink, brass + red accents.
  var c = {
    pageBg: '#E7DECF',
    bg: '#FBF7EF',
    surface: '#FFFDF8',
    surfaceAlt: '#EFE7DA',
    border: '#D1C5B6',
    text: '#2F271E',
    textMuted: '#665D54',
    textSubtle: '#7A6E61',
    accent: '#9A7445',
    accentHover: '#7D5B34',
    red: '#B12D15',
    redLight: '#C8402A'
  };

  var serif = "Georgia, 'Times New Roman', serif";
  var sans = "-apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

  // Localized strings (headline is impersonal / showroom-safe \u2014 no first name).
  var L = isEs ? {
    eyebrow: 'TUS RESULTADOS',
    headline: 'Tu match de sue\u00f1o WG&R est\u00e1 listo',
    headlineAccent: 'match de sue\u00f1o WG&R',
    bestLabel: 'TU MEJOR OPCI\u00d3N',
    bestStart: 'El mejor punto de partida en la tienda.',
    matchSuffix: 'compatibilidad',
    comparisonOption: 'Opci\u00f3n adicional para comparar',
    briefLabel: 'TU RESUMEN DE SUE\u00d1O',
    savingsLabel: 'TU PASE DE AHORRO DE 30 D\u00cdAS',
    savingsHint: discount + '% DE DESCUENTO en ' + passScope,
    savingsExpiry: 'V\u00e1lido hasta ' + passExpiration,
    savingsTerms: passTerms,
    moreLabel: 'M\u00c1S OPCIONES PARA COMPARAR',
    accLabel: 'TU SISTEMA DE SUE\u00d1O GUARDADO',
    ctaMain: 'Lleva este correo a tu especialista de sue\u00f1o de ' + storeName + ' \u2014 tendr\u00e1n tus opciones listas.',
    helpedBy: rsa ? 'Atendido por ' + rsa + ' en ' + storeName : '',
    ctaSaved: 'Tu Pase de Ahorro est\u00e1 guardado. T\u00f3mate tu tiempo.',
    unsubWhy: 'Recibiste este correo porque guardaste tu Resumen de Sue\u00f1o en ' + storeName + '.',
    unsubAction: 'Cancelar suscripci\u00f3n',
    privacyLine: 'Privacidad y solicitudes de datos: ' + PRIVACY_CONTACT,
    viewSite: 'Ver en el sitio de WG&amp;R'
  } : {
    eyebrow: 'YOUR RESULTS',
    headline: 'Your WG&R sleep match is ready',
    headlineAccent: 'WG&R sleep match',
    bestLabel: 'YOUR BEST MATCH',
    bestStart: 'Best place to start in-store.',
    matchSuffix: 'match',
    comparisonOption: 'Additional comparison option',
    briefLabel: 'YOUR SLEEP BRIEF',
    savingsLabel: 'YOUR 30-DAY SAVINGS PASS',
    savingsHint: discount + '% OFF ' + passScope,
    savingsExpiry: 'Good through ' + passExpiration,
    savingsTerms: passTerms,
    moreLabel: 'MORE MATCHES TO COMPARE',
    accLabel: 'YOUR SAVED SLEEP SYSTEM',
    ctaMain: 'Bring this email to your ' + storeName + ' sleep specialist \u2014 they\u2019ll have your picks ready.',
    helpedBy: rsa ? 'Helped by ' + rsa + ' at ' + storeName : '',
    ctaSaved: 'Your Savings Pass is saved. Take your time.',
    unsubWhy: 'You received this email because you saved your Sleep Brief at ' + storeName + '.',
    unsubAction: 'Unsubscribe',
    privacyLine: 'Privacy & data requests: ' + PRIVACY_CONTACT,
    viewSite: "View on WG&amp;R\u2019s site"
  };

  // Render the headline: escape the raw "WG&R" ampersand and italicize the brand
  // phrase in brass. Static copy (not user input).
  function headlineHtml() {
    var h = L.headline.split('&').join('&amp;');
    var a = L.headlineAccent.split('&').join('&amp;');
    return h.split(a).join('<em style="color:' + c.accent + ';font-style:italic;">' + a + '</em>');
  }

  // Helper: one mattress card. hero=true => elevated top-match treatment with a
  // red rule, larger name, a brass match-chip, and the showroom start line.
  function mattressCard(m, hero) {
    var name = _escapeHtml(m.name || '');
    var brand = _escapeHtml(m.brand || '');
    var pct = _escapeHtml(m.matchPct || '');
    var meets = m.meetsMatchThreshold === true;
    var img = _escapeHtml(m.imageUrl || '');
    if (hero) {
      var chip = meets
        ? '<span style="display:inline-block;background:' + c.accent + ';color:' + c.surface + ';font-family:' + sans + ';font-size:13px;font-weight:700;letter-spacing:0.5px;padding:5px 12px;border-radius:3px;">' + pct + '% ' + L.matchSuffix + '</span>'
        : '<span style="display:inline-block;background:' + c.surfaceAlt + ';color:' + c.textMuted + ';font-family:' + sans + ';font-size:12px;font-weight:600;padding:5px 12px;border-radius:3px;border:1px solid ' + c.border + ';">' + L.comparisonOption + '</span>';
      var heroImg = '<td width="110" valign="middle" style="padding:0;background:' + c.surfaceAlt + ';border-right:1px solid ' + c.border + ';">'
        + (img
            ? '<img src="' + img + '" width="110" height="108" alt="' + name + '" style="display:block;border:0;width:110px;height:108px;object-fit:cover;background:' + c.surfaceAlt + ';">'
            : '<div style="width:110px;height:108px;background:' + c.surfaceAlt + ';"></div>')
        + '</td>';
      return ''
        + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';border-left:4px solid ' + c.red + ';margin-bottom:6px;border-radius:3px;">'
        + '<tr>'
        + heroImg
        + '<td valign="middle" style="padding:18px 20px;">'
        + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.red + ';text-transform:uppercase;font-weight:700;margin-bottom:8px;">' + L.bestLabel + '</div>'
        + '<div style="font-family:' + serif + ';font-size:25px;color:' + c.text + ';font-weight:normal;line-height:1.15;margin-bottom:5px;">' + name + '</div>'
        + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.textMuted + ';margin-bottom:12px;">' + brand + '</div>'
        + chip
        + '<div style="font-family:' + sans + ';font-size:11px;color:' + c.textSubtle + ';margin-top:10px;">' + L.bestStart + '</div>'
        + '</td>'
        + '</tr>'
        + '</table>';
    }
    var matchLine = meets ? pct + '% ' + L.matchSuffix : L.comparisonOption;
    var imgCell = '<td width="80" valign="middle" style="padding:0;background:' + c.surfaceAlt + ';border-right:1px solid ' + c.border + ';">'
      + (img
          ? '<img src="' + img + '" width="80" height="72" alt="' + name + '" style="display:block;border:0;width:80px;height:72px;object-fit:cover;background:' + c.surfaceAlt + ';">'
          : '<div style="width:80px;height:72px;background:' + c.surfaceAlt + ';"></div>')
      + '</td>';
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:8px;border-radius:3px;">'
      + '<tr>'
      + imgCell
      + '<td valign="middle" style="padding:12px 16px;">'
      + '<div style="font-family:' + serif + ';font-size:16px;color:' + c.text + ';font-weight:normal;line-height:1.2;margin-bottom:3px;">' + name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;color:' + c.textMuted + ';margin-bottom:5px;">' + brand + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;">' + matchLine + '</div>'
      + '</td>'
      + '</tr>'
      + '</table>';
  }

  var topMatch = matches.length ? matches[0] : null;
  var heroCard = topMatch ? mattressCard(topMatch, true) : '';
  var secondaryRows = matches.slice(1).map(function(m) { return mattressCard(m, false); }).join('');

  // Accessories - single column rows (Outlook table-cell math is unreliable).
  var accRows = accs.map(function(a) {
    var name = _escapeHtml(a.name || '');
    var category = _escapeHtml(a.category || '');
    var img = _escapeHtml(a.imageUrl || '');
    return ''
      + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.surface + ';border:1px solid ' + c.border + ';margin-bottom:8px;border-radius:3px;">'
      + '<tr>'
      + '<td width="60" valign="middle" style="padding:0;background:' + c.surfaceAlt + ';">'
      + (img
          ? '<img src="' + img + '" width="60" height="60" alt="' + name + '" style="display:block;border:0;width:60px;height:60px;object-fit:cover;">'
          : '<div style="width:60px;height:60px;background:' + c.surfaceAlt + ';"></div>')
      + '</td>'
      + '<td valign="middle" style="padding:10px 14px;">'
      + '<div style="font-family:' + serif + ';font-size:14px;color:' + c.text + ';line-height:1.2;">' + name + '</div>'
      + '<div style="font-family:' + sans + ';font-size:11px;letter-spacing:1.5px;color:' + c.textSubtle + ';text-transform:uppercase;margin-top:3px;">' + category + '</div>'
      + '</td>'
      + '</tr>'
      + '</table>';
  }).join('');

  var accSection = accs.length > 0
    ? '<tr><td style="padding:8px 32px 24px;">'
      + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.accLabel + '</div>'
      + accRows
      + '</td></tr>'
    : '';

  // Website-derived WG&R offers - calmer than hero/brief (brass label + badges,
  // smaller type) so it does not overpower the top match and Sleep Brief.
  var promos = Array.isArray(data.promotions) ? data.promotions : [];
  var promoDisclosure = (data.promoDisclosure || '').toString();
  var promoHeader = promoDisclosure
    ? (isEs ? 'Ofertas de WG&amp;R' : 'WG&amp;R Offers')
    : (isEs ? 'Ofertas Actuales de WG&amp;R' : 'Current WG&amp;R Offers');
  var promoSection = promos.length > 0
    ? '<tr><td style="padding:4px 32px 22px;">'
      + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:8px;">'
      + promoHeader + '</div>'
      + (promoDisclosure ? '<div style="font-family:' + sans + ';font-size:10px;font-weight:600;color:' + c.accent + ';background:rgba(154,116,69,0.08);border:1px solid ' + c.border + ';border-radius:2px;padding:8px 10px;margin-bottom:10px;line-height:1.45;">' + _escapeHtml(promoDisclosure) + '</div>' : '')
      + (data.promoSpanishDraft ? '<div style="font-family:' + sans + ';font-size:10px;font-style:italic;color:' + c.textSubtle + ';margin-bottom:10px;">' + _escapeHtml(data.promoSpanishDraft) + '</div>' : '')
      + promos.map(function(p) {
          return '<div style="border-top:1px solid ' + c.border + ';padding:9px 0;">'
            + '<div style="font-family:' + sans + ';font-size:10px;font-weight:700;color:' + c.accent + ';letter-spacing:0.5px;text-transform:uppercase;">' + _escapeHtml(p.badge) + '</div>'
            + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.text + ';margin-top:3px;line-height:1.4;">' + _escapeHtml(p.headline) + '</div>'
            + (p.detail ? '<div style="font-family:' + sans + ';font-size:10px;color:' + c.textMuted + ';margin-top:2px;line-height:1.5;">' + _escapeHtml(p.detail) + '</div>' : '')
            + (p.disclosure ? '<div style="font-family:' + sans + ';font-size:10px;color:' + c.textSubtle + ';margin-top:2px;line-height:1.45;">' + _escapeHtml(p.disclosure) + '</div>' : '')
            + (p.provenance ? '<div style="font-family:' + sans + ';font-size:10px;color:' + c.textSubtle + ';margin-top:2px;line-height:1.45;">' + _escapeHtml(p.provenance) + '</div>' : '')
            + (p.expiration ? '<div style="font-family:' + sans + ';font-size:10px;color:' + c.textSubtle + ';font-weight:600;margin-top:2px;">' + _escapeHtml(p.expiration) + '</div>' : '')
            + (p.sourceUrl ? '<div style="font-family:' + sans + ';font-size:10px;margin-top:2px;"><a href="' + _escapeHtml(p.sourceUrl) + '" style="color:' + c.accent + ';">' + L.viewSite + '</a></div>' : '')
            + '</div>';
        }).join('')
      + '</td></tr>'
    : '';

  return ''
    + '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    + '<html xmlns="http://www.w3.org/1999/xhtml">'
    + '<head>'
    + '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<title>WG&amp;R Sleep Match</title>'
    + '<!--[if mso]><style>td,div,p,a {font-family: Georgia, "Times New Roman", serif !important;}</style><![endif]-->'
    + '</head>'
    + '<body style="margin:0;padding:0;background:' + c.pageBg + ';">'
    + '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.pageBg + ';">'
    + '<tr><td align="center" style="padding:24px 12px;">'
    + '<table width="600" cellpadding="0" cellspacing="0" border="0" role="presentation" style="background:' + c.bg + ';max-width:600px;width:100%;border:1px solid ' + c.border + ';">'

    + '<tr><td style="height:4px;background:' + c.red + ';font-size:0;line-height:0;">&nbsp;</td></tr>'

    + '<tr><td style="padding:30px 32px 24px;text-align:center;border-bottom:1px solid ' + c.border + ';">'
    + '<div style="font-family:' + serif + ';font-size:30px;line-height:1;color:' + c.red + ';font-weight:700;letter-spacing:0.5px;">WG&amp;R'
    + '<span style="font-family:' + sans + ';font-size:13px;letter-spacing:3px;color:' + c.textMuted + ';text-transform:lowercase;font-weight:400;"> furniture</span></div>'
    + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:3px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin:18px 0 10px;">' + L.eyebrow + '</div>'
    + '<div style="font-family:' + serif + ';font-size:26px;line-height:1.25;color:' + c.text + ';font-weight:normal;">' + headlineHtml() + '</div>'
    + '</td></tr>'

    + (heroCard ? '<tr><td style="padding:24px 32px 8px;">' + heroCard + '</td></tr>' : '')

    + (sleepProfile
        ? '<tr><td style="padding:8px 32px 16px;">'
          + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:8px;">' + L.briefLabel + '</div>'
          + '<div style="font-family:' + serif + ';font-size:17px;color:' + c.text + ';line-height:1.35;">' + sleepProfile + '</div>'
          + '</td></tr>'
        : '')

    + (dreamCode
        ? '<tr><td style="background:' + c.surfaceAlt + ';border-top:1px solid ' + c.border + ';border-bottom:1px solid ' + c.border + ';padding:28px 32px;text-align:center;">'
          + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:3px;color:' + c.red + ';text-transform:uppercase;font-weight:700;margin-bottom:12px;">' + L.savingsLabel + '</div>'
          + '<div style="font-family:' + serif + ';font-size:34px;letter-spacing:5px;color:' + c.accent + ';line-height:1;margin-bottom:12px;">' + dreamCode + '</div>'
          + '<div style="font-family:' + sans + ';font-size:13px;color:' + c.text + ';margin-bottom:6px;">' + L.savingsHint + '</div>'
          + '<div style="font-family:' + sans + ';font-size:12px;color:' + c.red + ';font-weight:600;margin-bottom:10px;">' + L.savingsExpiry + '</div>'
          + '<div style="font-family:' + sans + ';font-size:11px;line-height:1.5;color:' + c.textMuted + ';">' + L.savingsTerms + '</div>'
          + '</td></tr>'
        : '')

    + promoSection

    + (secondaryRows
        ? '<tr><td style="padding:16px 32px 8px;">'
          + '<div style="font-family:' + sans + ';font-size:10px;letter-spacing:2.5px;color:' + c.accent + ';text-transform:uppercase;font-weight:600;margin-bottom:14px;">' + L.moreLabel + '</div>'
          + secondaryRows
          + '</td></tr>'
        : '')

    + accSection

    + '<tr><td style="padding:24px 32px 14px;text-align:center;border-top:1px solid ' + c.border + ';">'
    + '<div style="font-family:' + sans + ';font-size:13px;color:' + c.text + ';margin-bottom:8px;line-height:1.5;">' + L.ctaMain + '</div>'
    + (L.helpedBy ? '<div style="font-family:' + sans + ';font-size:12px;color:' + c.textMuted + ';margin-bottom:8px;">' + L.helpedBy + '</div>' : '')
    + '<div style="font-family:' + serif + ';font-size:17px;color:' + c.red + ';font-style:italic;line-height:1.3;">' + L.ctaSaved + '</div>'
    + '</td></tr>'

    + '<tr><td style="padding:8px 32px 28px;text-align:center;">'
    + '<div style="font-family:' + sans + ';font-size:10px;color:' + c.textSubtle + ';line-height:1.7;border-top:1px solid ' + c.border + ';padding-top:16px;">'
    + L.unsubWhy + '<br>'
    + _escapeHtml(POSTAL_ADDRESS) + '<br>'
    + '<a href="' + _escapeHtml(UNSUBSCRIBE_URL) + '" style="color:' + c.textSubtle + ';">' + _escapeHtml(L.unsubAction) + '</a>'
    + ' &nbsp;&middot;&nbsp; ' + _escapeHtml(L.privacyLine)
    + '</div>'
    + '</td></tr>'

    + '</table>'
    + '</td></tr></table>'
    + '</body></html>';
}
